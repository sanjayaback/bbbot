import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from redis import Redis
from rq import Queue, Retry
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db import get_db
from apps.api.security import Principal, current_principal, require_workspace_role
from packages.security.audit import write_audit

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/{document_id}/reindex", status_code=202)
async def reindex_document(
    document_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            text(
                """
                SELECT d.workspace_id, v.id AS version_id, v.status
                FROM documents d
                JOIN LATERAL (
                    SELECT id, status
                    FROM document_versions
                    WHERE document_id=d.id
                    ORDER BY version_no DESC
                    LIMIT 1
                ) v ON true
                WHERE d.id=:document_id AND d.archived_at IS NULL
                """
            ),
            {"document_id": document_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Document not found")

    workspace_id = str(row["workspace_id"])
    version_id = str(row["version_id"])
    await require_workspace_role(workspace_id, principal, db, {"owner", "admin", "editor"})

    active = (
        await db.execute(
            text(
                """
                SELECT id FROM document_jobs
                WHERE document_version_id=:version_id
                  AND status IN ('queued','extracting','chunking','embedding')
                ORDER BY created_at DESC LIMIT 1
                """
            ),
            {"version_id": version_id},
        )
    ).scalar_one_or_none()
    if active:
        raise HTTPException(409, "Document is already being processed")

    job_id = str(uuid.uuid4())
    await db.execute(
        text(
            """
            INSERT INTO document_jobs(id,workspace_id,document_version_id,job_type,status,progress)
            VALUES(:id,:workspace_id,:version_id,'reindex','queued',0)
            """
        ),
        {"id": job_id, "workspace_id": workspace_id, "version_id": version_id},
    )
    await db.execute(
        text("UPDATE document_versions SET status='queued' WHERE id=:version_id"),
        {"version_id": version_id},
    )
    await write_audit(
        db,
        workspace_id=workspace_id,
        actor_user_id=principal.user_id,
        action="document.reindex_requested",
        resource_type="document",
        resource_id=document_id,
        request_id=request.state.request_id,
        ip=request.client.host if request.client else None,
        metadata={
            "embedding_provider": settings.embedding_provider,
            "local_embed_model": settings.local_embed_model
            if settings.embedding_provider.lower() == "local"
            else None,
            "gemini_embed_model": settings.gemini_embed_model
            if settings.embedding_provider.lower() == "gemini"
            else None,
        },
    )
    await db.commit()

    try:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=5, socket_timeout=5)
        redis.ping()
        Queue("docuquery", connection=redis).enqueue(
            "apps.worker.tasks.ingest_document",
            job_id,
            retry=Retry(max=3),
            job_timeout=1800,
        )
    except Exception as exc:
        await db.execute(
            text(
                """
                UPDATE document_jobs
                SET status='failed',error_message=:error,updated_at=now(),finished_at=now()
                WHERE id=:job_id
                """
            ),
            {"error": f"Queue unavailable: {type(exc).__name__}"[:2000], "job_id": job_id},
        )
        await db.execute(
            text("UPDATE document_versions SET status='failed' WHERE id=:version_id"),
            {"version_id": version_id},
        )
        await db.commit()
        raise HTTPException(503, "Reindex job could not be queued") from exc

    return {
        "document_id": document_id,
        "version_id": version_id,
        "job_id": job_id,
        "status": "queued",
        "embedding_provider": settings.embedding_provider,
    }
