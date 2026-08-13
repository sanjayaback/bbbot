import hashlib
import os
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from redis import Redis
from rq import Queue, Retry
from apps.api.config import settings
from apps.api.db import get_db
from apps.api.security import Principal, current_principal, require_workspace_role
from packages.storage.factory import storage_backend
from packages.ingestion.validate import validate_upload
from packages.security.malware import scan_bytes
from packages.security.quota import ensure_storage_quota
from packages.security.audit import write_audit

router=APIRouter(prefix="/api/documents",tags=["documents"])


@router.post("/upload", status_code=202)
async def upload_document(request: Request, workspace_id:str=Form(...), knowledge_base_id:str=Form(...), file:UploadFile=File(...), p:Principal=Depends(current_principal), db:AsyncSession=Depends(get_db)):
    await require_workspace_role(workspace_id,p,db,{"owner","admin","editor"})
    kb=(await db.execute(text("SELECT id FROM knowledge_bases WHERE id=:k AND workspace_id=:w"),{"k":knowledge_base_id,"w":workspace_id})).scalar_one_or_none()
    if not kb: raise HTTPException(404,"Knowledge base not found")
    raw=await file.read()
    validate_upload(file.filename or "upload", file.content_type or "", raw, settings.max_upload_mb)
    scan_bytes(raw)
    await ensure_storage_quota(db,workspace_id,len(raw))
    sha=hashlib.sha256(raw).hexdigest()
    existing=(await db.execute(text("""
      SELECT d.id FROM documents d JOIN document_versions v ON v.document_id=d.id
      WHERE d.workspace_id=:w AND d.knowledge_base_id=:k AND v.sha256=:h AND d.archived_at IS NULL LIMIT 1
    """),{"w":workspace_id,"k":knowledge_base_id,"h":sha})).scalar_one_or_none()
    if existing: raise HTTPException(409,"This exact document is already uploaded in the knowledge base")

    doc_id, ver_id, job_id = map(lambda _: str(uuid.uuid4()), range(3))
    safe_name=os.path.basename(file.filename or "document")
    storage_path=f"{workspace_id}/{doc_id}/{ver_id}/{safe_name}"
    try:
        storage_backend().put(storage_path, raw, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(502,"Could not store uploaded document") from exc

    await db.execute(text("INSERT INTO documents(id,workspace_id,knowledge_base_id,name,created_by) VALUES(:id,:w,:k,:n,:u)"),{"id":doc_id,"w":workspace_id,"k":knowledge_base_id,"n":safe_name,"u":p.user_id})
    await db.execute(text("INSERT INTO document_versions(id,document_id,version_no,storage_path,sha256,mime_type,file_size,status) VALUES(:id,:d,1,:s,:h,:m,:z,'queued')"),{"id":ver_id,"d":doc_id,"s":storage_path,"h":sha,"m":file.content_type,"z":len(raw)})
    await db.execute(text("INSERT INTO document_jobs(id,workspace_id,document_version_id,job_type,status,progress) VALUES(:id,:w,:v,'ingest','queued',0)"),{"id":job_id,"w":workspace_id,"v":ver_id})
    await db.execute(text("INSERT INTO usage_events(workspace_id,user_id,operation,storage_bytes) VALUES(:w,:u,'document_upload',:z)"),{"w":workspace_id,"u":p.user_id,"z":len(raw)})
    await write_audit(db,workspace_id=workspace_id,actor_user_id=p.user_id,action="document.uploaded",resource_type="document",resource_id=doc_id,request_id=request.state.request_id,ip=request.client.host if request.client else None,metadata={"filename":safe_name,"size":len(raw)})
    await db.commit()
    Queue("docuquery", connection=Redis.from_url(settings.redis_url)).enqueue("apps.worker.tasks.ingest_document", job_id, retry=Retry(max=3), job_timeout=1800)
    return {"document_id":doc_id,"version_id":ver_id,"job_id":job_id,"status":"queued"}


@router.get("")
async def list_documents(workspace_id:str, knowledge_base_id:str|None=None,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    await require_workspace_role(workspace_id,p,db,{"owner","admin","editor","viewer"})
    rows=(await db.execute(text("""
      SELECT d.id,d.name,d.knowledge_base_id,k.name AS knowledge_base_name,d.created_at,dv.status,dv.version_no,dv.file_size,dv.id AS version_id
      FROM documents d JOIN knowledge_bases k ON k.id=d.knowledge_base_id
      LEFT JOIN LATERAL (SELECT * FROM document_versions v WHERE v.document_id=d.id ORDER BY version_no DESC LIMIT 1) dv ON true
      WHERE d.workspace_id=:w AND d.archived_at IS NULL AND (CAST(:k AS uuid) IS NULL OR d.knowledge_base_id=CAST(:k AS uuid))
      ORDER BY d.created_at DESC
    """),{"w":workspace_id,"k":knowledge_base_id})).mappings().all()
    return list(rows)


@router.get("/{document_id}/status")
async def document_status(document_id:str,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(text("""
      SELECT d.workspace_id,v.id AS version_id,v.status,j.progress,j.error_message,j.updated_at
      FROM documents d JOIN document_versions v ON v.document_id=d.id
      LEFT JOIN LATERAL (SELECT * FROM document_jobs j2 WHERE j2.document_version_id=v.id ORDER BY created_at DESC LIMIT 1) j ON true
      WHERE d.id=:d ORDER BY v.version_no DESC LIMIT 1
    """),{"d":document_id})).mappings().first()
    if not row: raise HTTPException(404,"Document not found")
    await require_workspace_role(str(row['workspace_id']),p,db,{"owner","admin","editor","viewer"})
    return dict(row)


@router.get("/{document_id}/pages/{page_number}")
async def source_page(document_id:str,page_number:int,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(text("""
      SELECT d.workspace_id,d.name,p.page_number,p.section_title,p.cleaned_text,v.version_no
      FROM documents d JOIN document_versions v ON v.document_id=d.id JOIN document_pages p ON p.document_version_id=v.id
      WHERE d.id=:d AND p.page_number=:p ORDER BY v.version_no DESC LIMIT 1
    """),{"d":document_id,"p":page_number})).mappings().first()
    if not row: raise HTTPException(404,"Page not found")
    await require_workspace_role(str(row['workspace_id']),p,db,{"owner","admin","editor","viewer"})
    return dict(row)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id:str,request:Request,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(text("SELECT workspace_id FROM documents WHERE id=:d AND archived_at IS NULL"),{"d":document_id})).mappings().first()
    if not row: raise HTTPException(404,"Document not found")
    workspace_id=str(row['workspace_id'])
    await require_workspace_role(workspace_id,p,db,{"owner","admin","editor"})
    await db.execute(text("UPDATE documents SET archived_at=now() WHERE id=:d"),{"d":document_id})
    await write_audit(db,workspace_id=workspace_id,actor_user_id=p.user_id,action="document.archived",resource_type="document",resource_id=document_id,request_id=request.state.request_id,ip=request.client.host if request.client else None)
    await db.commit()

@router.get("/{document_id}/chunks/{chunk_id}")
async def source_chunk(document_id:str,chunk_id:str,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(text("""
      SELECT d.workspace_id,d.name,c.id AS chunk_id,c.content,p.page_number,p.section_title,v.version_no
      FROM chunks c JOIN document_versions v ON v.id=c.document_version_id JOIN documents d ON d.id=v.document_id
      LEFT JOIN document_pages p ON p.id=c.page_id
      WHERE d.id=:d AND c.id=:c LIMIT 1
    """),{"d":document_id,"c":chunk_id})).mappings().first()
    if not row: raise HTTPException(404,"Source chunk not found")
    await require_workspace_role(str(row['workspace_id']),p,db,{"owner","admin","editor","viewer"})
    return dict(row)
