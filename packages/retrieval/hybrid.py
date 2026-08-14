from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from packages.retrieval.reranker import heuristic_rerank


async def hybrid_retrieve(
    db: AsyncSession,
    workspace_id: str,
    embedding: list[float],
    question: str,
    sources: list[dict],
    limit: int = 8,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
):
    vec='['+','.join(f'{x:.8f}' for x in embedding)+']'
    kb_ids=[str(s['source_id']) for s in sources if s['source_type']=='knowledge_base']
    doc_ids=[str(s['source_id']) for s in sources if s['source_type']=='document']
    sql="""WITH ranked AS (
      SELECT c.id AS chunk_id,c.content,p.page_number,p.section_title,d.id AS document_id,d.name AS document_name,
             v.version_no,
             1-(e.embedding <=> CAST(:vec AS vector)) AS vector_score,
             ts_rank_cd(to_tsvector('simple',c.content), plainto_tsquery('simple',:q)) AS fts_score
      FROM chunks c
      JOIN chunk_embeddings e ON e.chunk_id=c.id
      JOIN document_versions v ON v.id=c.document_version_id
      JOIN documents d ON d.id=v.document_id
      LEFT JOIN document_pages p ON p.id=c.page_id
      WHERE c.workspace_id=:w AND v.status='ready' AND d.archived_at IS NULL
        AND (:embedding_provider IS NULL OR e.provider=:embedding_provider)
        AND (:embedding_model IS NULL OR e.model=:embedding_model)
        AND (:has_sources=false OR (
          (:use_kb=true AND d.knowledge_base_id = ANY(CAST(:kb AS uuid[]))) OR
          (:use_doc=true AND d.id = ANY(CAST(:docs AS uuid[])))
        ))
    )
    SELECT *, (vector_score*0.75 + LEAST(fts_score,1)*0.25) AS score
    FROM ranked ORDER BY score DESC LIMIT :candidate_limit"""
    params={
        "vec":vec,"q":question,"w":workspace_id,"has_sources":bool(kb_ids or doc_ids),
        "use_kb":bool(kb_ids),"kb":kb_ids or None,"use_doc":bool(doc_ids),"docs":doc_ids or None,
        "embedding_provider":embedding_provider,"embedding_model":embedding_model,
        "candidate_limit":max(limit*4,24)
    }
    rows=(await db.execute(text(sql),params)).mappings().all()
    return heuristic_rerank(question,[dict(r) for r in rows],limit=limit)
