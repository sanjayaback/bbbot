from fastapi import APIRouter,Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.db import get_db
from apps.api.security import Principal,current_principal,require_workspace_role

router=APIRouter(prefix="/api/activity",tags=["activity"])


@router.get("")
async def activity(workspace_id:str,limit:int=50,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    await require_workspace_role(workspace_id,p,db,{"owner","admin","editor","viewer"})
    rows=(await db.execute(text("""
      SELECT a.id,a.action,a.resource_type,a.resource_id,a.created_at,a.metadata,p.email AS actor_email
      FROM audit_logs a LEFT JOIN profiles p ON p.id=a.actor_user_id
      WHERE a.workspace_id=:w ORDER BY a.created_at DESC LIMIT :lim
    """),{"w":workspace_id,"lim":min(max(limit,1),200)})).mappings().all()
    return list(rows)
