import asyncio
import json
import uuid
from sqlalchemy import text
from apps.api.db import SessionLocal
from packages.storage.factory import storage_backend
from packages.ingestion.parsers import parse_document
from packages.ingestion.chunker import smart_chunks
from packages.ai.factory import create_embedder
from packages.ai.credentials import resolve_gemini_key
from apps.api.config import settings


async def _run(job_id:str):
    async with SessionLocal() as db:
        row=(await db.execute(text("""
          SELECT j.document_version_id,v.storage_path,v.mime_type,d.workspace_id
          FROM document_jobs j JOIN document_versions v ON v.id=j.document_version_id
          JOIN documents d ON d.id=v.document_id WHERE j.id=:j
        """),{"j":job_id})).mappings().one()

        async def status(s,p,error=None,finished=False):
            await db.execute(text("""
              UPDATE document_jobs SET status=:s,progress=:p,error_message=:e,
                attempt=CASE WHEN :s='extracting' THEN attempt+1 ELSE attempt END,
                started_at=COALESCE(started_at,now()),updated_at=now(),finished_at=CASE WHEN :f THEN now() ELSE finished_at END
              WHERE id=:j
            """),{"s":s,"p":p,"e":error,"j":job_id,"f":finished})
            await db.execute(text("UPDATE document_versions SET status=:s WHERE id=:v"),{"s":s,"v":row['document_version_id']})
            await db.commit()

        try:
            await status('extracting',10)
            data=storage_backend().get(row['storage_path'])
            pages=parse_document(data,row['storage_path'],row['mime_type'])
            if not pages:
                raise ValueError("No readable text was extracted from the document")

            await status('chunking',35)
            # Idempotent reprocessing: remove previous derived page/chunk data for this version.
            await db.execute(text("DELETE FROM document_pages WHERE document_version_id=:v"),{"v":row['document_version_id']})
            await db.commit()
            chunks=[]
            for page in pages:
                pid=str(uuid.uuid4())
                await db.execute(text("""
                  INSERT INTO document_pages(id,document_version_id,page_number,section_title,raw_text,cleaned_text,metadata)
                  VALUES(:id,:v,:p,:s,:r,:c,CAST(:m AS jsonb))
                """),{"id":pid,"v":row['document_version_id'],"p":page.page_number,"s":page.section,"r":page.text,"c":page.text,"m":json.dumps({"extraction_method":page.extraction_method})})
                for idx,chunk in enumerate(smart_chunks(page.text)):
                    chunks.append((pid,page,idx,chunk))
            await db.commit()
            if not chunks:
                raise ValueError("Document produced no searchable chunks")

            await status('embedding',50)
            api_key = None
            if settings.embedding_provider.lower() == 'gemini':
                api_key = await resolve_gemini_key(db,str(row['workspace_id']))
            embedder=create_embedder(api_key)
            embed_document = getattr(embedder, 'embed_document', embedder.embed)
            provider = getattr(embedder, 'provider', settings.embedding_provider.lower())
            for n,(pid,page,idx,chunk) in enumerate(chunks):
                vec=await embed_document(chunk)
                if len(vec) != settings.embedding_dimension:
                    raise RuntimeError(
                        f"Embedding dimension {len(vec)} does not match configured vector dimension {settings.embedding_dimension}"
                    )
                cid=str(uuid.uuid4())
                vector='['+','.join(f'{x:.8f}' for x in vec)+']'
                await db.execute(text("""
                  INSERT INTO chunks(id,workspace_id,document_version_id,page_id,chunk_index,content,token_count,metadata)
                  VALUES(:id,:w,:v,:p,:i,:c,:t,CAST(:m AS jsonb))
                """),{"id":cid,"w":row['workspace_id'],"v":row['document_version_id'],"p":pid,"i":idx,"c":chunk,"t":max(1,len(chunk)//4),"m":json.dumps({"section":page.section})})
                await db.execute(text("""
                  INSERT INTO chunk_embeddings(id,chunk_id,provider,model,dimension,embedding_version,embedding)
                  VALUES(:id,:c,:provider,:m,:d,1,CAST(:e AS vector))
                """),{"id":str(uuid.uuid4()),"c":cid,"provider":provider,"m":embedder.model,"d":len(vec),"e":vector})
                if n % 10 == 0 or n == len(chunks)-1:
                    await db.commit()
                    await status('embedding',50+int(45*(n+1)/len(chunks)))
            await status('ready',100,finished=True)
        except Exception as exc:
            await db.rollback()
            await status('failed',0,str(exc)[:2000],finished=True)
            raise


def ingest_document(job_id:str):
    asyncio.run(_run(job_id))
