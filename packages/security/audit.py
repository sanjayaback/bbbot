import json
import uuid
from sqlalchemy import text


async def write_audit(db, *, workspace_id, actor_user_id, action, resource_type=None, resource_id=None, request_id=None, ip=None, metadata=None):
    await db.execute(text("""
        INSERT INTO audit_logs(id,workspace_id,actor_user_id,action,resource_type,resource_id,request_id,ip,metadata)
        VALUES(:id,:w,:u,:a,:rt,:rid,:req,CAST(:ip AS inet),CAST(:m AS jsonb))
    """), {
        "id": str(uuid.uuid4()), "w": workspace_id, "u": actor_user_id, "a": action,
        "rt": resource_type, "rid": resource_id, "req": request_id, "ip": ip,
        "m": json.dumps(metadata or {}),
    })
