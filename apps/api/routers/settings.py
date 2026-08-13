import uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.config import settings
from apps.api.db import get_db
from apps.api.schemas import CredentialSave
from apps.api.security import Principal,current_principal,require_workspace_role
from packages.security.crypto import CredentialCipher
from packages.security.audit import write_audit

router=APIRouter(prefix="/api/settings",tags=["settings"])


@router.get("")
async def get_settings(workspace_id:str,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    role=await require_workspace_role(workspace_id,p,db,{"owner","admin","editor","viewer"})
    key=(await db.execute(text("SELECT provider,key_hint,created_at FROM api_credentials WHERE workspace_id=:w ORDER BY created_at DESC LIMIT 1"),{"w":workspace_id})).mappings().first()
    ws=(await db.execute(text("""
      SELECT plan,monthly_question_limit,storage_limit_bytes,
       (SELECT count(*) FROM usage_events u WHERE u.workspace_id=w.id AND u.operation='chat_question' AND u.created_at>=date_trunc('month',now())) AS questions_used,
       COALESCE((SELECT sum(v.file_size) FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE d.workspace_id=w.id),0) AS storage_used
      FROM workspaces w WHERE w.id=:w
    """),{"w":workspace_id})).mappings().one()
    return {"role":role,"provider_credential":dict(key) if key else None,"usage":dict(ws),"managed_gemini_configured":bool(settings.gemini_api_key),"ai_mode":settings.ai_mode}


@router.post("/credentials")
async def save_credential(body:CredentialSave,request:Request,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    await require_workspace_role(body.workspace_id,p,db,{"owner","admin"})
    if not settings.credential_encryption_key:
        raise HTTPException(503,"Credential encryption is not configured")
    cipher=CredentialCipher(settings.credential_encryption_key)
    enc=cipher.encrypt(body.secret)
    hint=f"...{body.secret[-4:]}"
    await db.execute(text("DELETE FROM api_credentials WHERE workspace_id=:w AND provider=:p"),{"w":body.workspace_id,"p":body.provider})
    await db.execute(text("INSERT INTO api_credentials(id,workspace_id,provider,encrypted_secret,key_hint,created_by) VALUES(:id,:w,:p,:s,:h,:u)"),{"id":str(uuid.uuid4()),"w":body.workspace_id,"p":body.provider,"s":enc,"h":hint,"u":p.user_id})
    await write_audit(db,workspace_id=body.workspace_id,actor_user_id=p.user_id,action="credential.saved",resource_type="api_credential",request_id=request.state.request_id,ip=request.client.host if request.client else None,metadata={"provider":body.provider,"hint":hint})
    await db.commit()
    return {"provider":body.provider,"key_hint":hint}


@router.delete("/credentials/{provider}", status_code=204)
async def delete_credential(provider:str,workspace_id:str,request:Request,p:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    await require_workspace_role(workspace_id,p,db,{"owner","admin"})
    await db.execute(text("DELETE FROM api_credentials WHERE workspace_id=:w AND provider=:p"),{"w":workspace_id,"p":provider})
    await write_audit(db,workspace_id=workspace_id,actor_user_id=p.user_id,action="credential.deleted",resource_type="api_credential",request_id=request.state.request_id,ip=request.client.host if request.client else None,metadata={"provider":provider})
    await db.commit()
