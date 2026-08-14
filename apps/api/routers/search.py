from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db import get_db
from apps.api.security import Principal, current_principal, require_workspace_role
from packages.ai.credentials import resolve_gemini_key
from packages.ai.factory import create_embedder
from packages.retrieval.context import build_context
from packages.retrieval.hybrid import hybrid_retrieve

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_evidence(
    workspace_id: str,
    q: str = Query(..., min_length=1, max_length=2000),
    knowledge_base_id: str | None = None,
    document_id: str | None = None,
    limit: int = Query(8, ge=1, le=20),
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve grounded document evidence without invoking any generative LLM."""
    await require_workspace_role(workspace_id, principal, db, {"owner", "admin", "editor", "viewer"})

    sources: list[dict] = []
    if knowledge_base_id:
        valid = (
            await db.execute(
                text("SELECT 1 FROM knowledge_bases WHERE id=:id AND workspace_id=:w"),
                {"id": knowledge_base_id, "w": workspace_id},
            )
        ).scalar_one_or_none()
        if not valid:
            raise HTTPException(404, "Knowledge base not found")
        sources.append({"source_type": "knowledge_base", "source_id": knowledge_base_id})

    if document_id:
        valid = (
            await db.execute(
                text("SELECT 1 FROM documents WHERE id=:id AND workspace_id=:w AND archived_at IS NULL"),
                {"id": document_id, "w": workspace_id},
            )
        ).scalar_one_or_none()
        if not valid:
            raise HTTPException(404, "Document not found")
        sources.append({"source_type": "document", "source_id": document_id})

    api_key = None
    if settings.embedding_provider.lower() == "gemini":
        api_key = await resolve_gemini_key(db, workspace_id)

    embedder = create_embedder(api_key)
    embed_query = getattr(embedder, "embed_query", embedder.embed)
    vector = await embed_query(q)
    if len(vector) != settings.embedding_dimension:
        raise HTTPException(503, "Embedding provider returned an incompatible vector dimension")

    embedding_provider = getattr(embedder, "provider", settings.embedding_provider.lower())
    embedding_model = getattr(embedder, "model", None)
    chunks = await hybrid_retrieve(
        db,
        workspace_id,
        vector,
        q,
        sources,
        limit=limit,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    _, citations = build_context(chunks)

    evidence = []
    for index, chunk in enumerate(chunks):
        evidence.append(
            {
                "rank": index + 1,
                "chunk_id": str(chunk["chunk_id"]),
                "document_id": str(chunk["document_id"]),
                "document": chunk["document_name"],
                "page": chunk.get("page_number"),
                "section": chunk.get("section_title"),
                "content": chunk["content"],
                "score": float(chunk.get("score") or 0),
            }
        )

    return {
        "mode": "search_only",
        "query": q,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "count": len(evidence),
        "evidence": evidence,
        "citations": citations,
    }
