from fastapi import HTTPException
from sqlalchemy import text


async def ensure_question_quota(db, workspace_id: str) -> None:
    row = (await db.execute(text("""
      SELECT COALESCE(monthly_question_limit,:d) AS lim,
             (SELECT count(*) FROM usage_events u WHERE u.workspace_id=w.id AND u.operation='chat_question' AND u.created_at >= date_trunc('month',now())) AS used
      FROM workspaces w WHERE w.id=:w
    """), {"w": workspace_id, "d": 1000})).mappings().one()
    if row["used"] >= row["lim"]:
        raise HTTPException(429, "Monthly question quota exceeded")


async def ensure_storage_quota(db, workspace_id: str, additional_bytes: int) -> None:
    row = (await db.execute(text("""
      SELECT COALESCE(storage_limit_bytes,2147483648) AS lim,
             COALESCE((SELECT sum(v.file_size) FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE d.workspace_id=w.id),0) AS used
      FROM workspaces w WHERE w.id=:w
    """), {"w": workspace_id})).mappings().one()
    if int(row["used"]) + additional_bytes > int(row["lim"]):
        raise HTTPException(413, "Workspace storage quota exceeded")
