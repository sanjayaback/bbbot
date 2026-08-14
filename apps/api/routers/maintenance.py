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

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


@router.post("/documents/{document_id}/reindex", status_code=202)
async def reindex_document(
    document_id: str,
    request: Request,
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            text(
                """
                SELECT d.workspace_id, v.id AS version_id
                FROM documents d
                JOIN document_versions v ON v.document_id=d.id
                WHERE d.id=:d AND d.archived_at IS NULL
                ORDER BY v.version_no DESC
                LIMIT 1
                """
            ),
            {"d": document_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Document not found")

    workspace_id = str(row["workspace_id"])
    await require_workspace_role(workspace_id, p, db, {"owner", "admin", "editor"})

    existing = (
        await db.execute(
            text(
                """
                SELECT id FROM document_jobs
                WHERE document_version_id=:v AND status IN ('queued','extracting','chunking','embedding')
                ORDER BY created_at DESC LIMIT 1
                """
            ),
            {"v": row["version_id"]},
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Document already has an active processing job")

    job_id = str(uuid.uuid4())
    await db.execute(
        text(
            """
            INSERT INTO document_jobs(id,workspace_id,document_version_id,job_type,status,progress)
            VALUES(:id,:w,:v,'reindex','queued',0)
            """
        ),
        {"id": job_id, "w": workspace_id, "v": row["version_id"]},
    )
    await db.execute(
        text("UPDATE document_versions SET status='queued' WHERE id=:v"),
        {"v": row["version_id"]},
    )
    await write_audit(
        db,
        workspace_id=workspace_id,
        actor_user_id=p.user_id,
        action="document.reindex_requested",
        resource_type="document",
        resource_id=document_id,
        request_id=request.state.request_id,
        ip=request.client.host if request.client else None,
        metadata={"embedding_provider": settings.embedding_provider},
    )
    await db.commit()

    try:
        Queue("docuquery", connection=Redis.from_url(settings.redis_url)).enqueue(
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
                SET status='failed',progress=0,error_message=:e,finished_at=now(),updated_at=now()
                WHERE id=:j
                """
            ),
            {"j": job_id, "e": f"Queue unavailable: {str(exc)[:500]}"},
        )
        await db.execute(
            text("UPDATE document_versions SET status='failed' WHERE id=:v"),
            {"v": row["version_id"]},
        )
        await db.commit()
        raise HTTPException(503, "Document reindex could not be queued") from exc

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
        "embedding_provider": settings.embedding_provider,
    }
