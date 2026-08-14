import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db import get_db
from apps.api.schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate, MemberByEmail, MemberUpsert, WorkspaceCreate, WorkspaceUpdate
from apps.api.security import Principal, current_principal, ensure_profile, require_workspace_role
from packages.security.audit import write_audit

router = APIRouter(prefix="/api", tags=["workspaces"])


@router.post("/workspaces", status_code=201)
async def create_workspace(body: WorkspaceCreate, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await ensure_profile(db, p)
    wid = str(uuid.uuid4())
    await db.execute(text("INSERT INTO workspaces(id,name,created_by) VALUES(:id,:n,:u)"), {"id": wid, "n": body.name, "u": p.user_id})
    await db.execute(text("INSERT INTO workspace_members(workspace_id,user_id,role,status) VALUES(:w,:u,'owner','active')"), {"w": wid, "u": p.user_id})
    await write_audit(db, workspace_id=wid, actor_user_id=p.user_id, action="workspace.created", resource_type="workspace", resource_id=wid, request_id=request.state.request_id, ip=request.client.host if request.client else None)
    await db.commit()
    return {"id": wid, "name": body.name, "role": "owner"}


@router.get("/workspaces")
async def list_workspaces(p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await ensure_profile(db, p)
    await db.commit()
    rows = (await db.execute(text("SELECT w.id,w.name,w.plan,wm.role,w.created_at FROM workspaces w JOIN workspace_members wm ON wm.workspace_id=w.id WHERE wm.user_id=:u AND wm.status='active' ORDER BY w.created_at DESC"), {"u": p.user_id})).mappings().all()
    return list(rows)


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, body: WorkspaceUpdate, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(workspace_id, p, db, {"owner", "admin"})
    await db.execute(text("UPDATE workspaces SET name=:n WHERE id=:w"), {"n": body.name, "w": workspace_id})
    await write_audit(db, workspace_id=workspace_id, actor_user_id=p.user_id, action="workspace.updated", resource_type="workspace", resource_id=workspace_id, request_id=request.state.request_id, ip=request.client.host if request.client else None)
    await db.commit()
    return {"id": workspace_id, "name": body.name}


@router.post("/knowledge-bases", status_code=201)
async def create_kb(body: KnowledgeBaseCreate, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(body.workspace_id, p, db, {"owner", "admin", "editor"})
    kid = str(uuid.uuid4())
    await db.execute(text("INSERT INTO knowledge_bases(id,workspace_id,name,description,created_by) VALUES(:id,:w,:n,:d,:u)"), {"id": kid, "w": body.workspace_id, "n": body.name, "d": body.description, "u": p.user_id})
    await write_audit(db, workspace_id=body.workspace_id, actor_user_id=p.user_id, action="knowledge_base.created", resource_type="knowledge_base", resource_id=kid, request_id=request.state.request_id, ip=request.client.host if request.client else None)
    await db.commit()
    return {"id": kid, "name": body.name, "description": body.description}


@router.get("/knowledge-bases")
async def list_kbs(workspace_id: str, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(workspace_id, p, db, {"owner", "admin", "editor", "viewer"})
    rows = (await db.execute(text("""
      SELECT k.id,k.name,k.description,k.created_at,count(d.id) AS document_count
      FROM knowledge_bases k LEFT JOIN documents d ON d.knowledge_base_id=k.id AND d.archived_at IS NULL
      WHERE k.workspace_id=:w GROUP BY k.id ORDER BY k.created_at DESC
    """), {"w": workspace_id})).mappings().all()
    return list(rows)


@router.patch("/knowledge-bases/{kb_id}")
async def update_kb(kb_id: str, body: KnowledgeBaseUpdate, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(text("SELECT workspace_id FROM knowledge_bases WHERE id=:id"), {"id": kb_id})).mappings().first()
    if not row:
        raise HTTPException(404, "Knowledge base not found")
    await require_workspace_role(str(row["workspace_id"]), p, db, {"owner", "admin", "editor"})
    await db.execute(text("UPDATE knowledge_bases SET name=:n,description=:d,updated_at=now() WHERE id=:id"), {"n": body.name, "d": body.description, "id": kb_id})
    await write_audit(db, workspace_id=str(row["workspace_id"]), actor_user_id=p.user_id, action="knowledge_base.updated", resource_type="knowledge_base", resource_id=kb_id, request_id=request.state.request_id, ip=request.client.host if request.client else None)
    await db.commit()
    return {"id": kb_id, "name": body.name, "description": body.description}


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_kb(kb_id: str, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(text("SELECT workspace_id FROM knowledge_bases WHERE id=:id"), {"id": kb_id})).mappings().first()
    if not row:
        raise HTTPException(404, "Knowledge base not found")
    await require_workspace_role(str(row["workspace_id"]), p, db, {"owner", "admin"})
    count = (await db.execute(text("SELECT count(*) FROM documents WHERE knowledge_base_id=:id AND archived_at IS NULL"), {"id": kb_id})).scalar_one()
    if count:
        raise HTTPException(409, "Knowledge base contains documents")
    await db.execute(text("DELETE FROM knowledge_bases WHERE id=:id"), {"id": kb_id})
    await write_audit(db, workspace_id=str(row["workspace_id"]), actor_user_id=p.user_id, action="knowledge_base.deleted", resource_type="knowledge_base", resource_id=kb_id, request_id=request.state.request_id, ip=request.client.host if request.client else None)
    await db.commit()


@router.get("/workspaces/{workspace_id}/members")
async def list_members(workspace_id: str, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(workspace_id, p, db, {"owner", "admin", "editor", "viewer"})
    rows = (await db.execute(text("SELECT wm.user_id,wm.role,wm.status,p.email,wm.created_at FROM workspace_members wm LEFT JOIN profiles p ON p.id=wm.user_id WHERE wm.workspace_id=:w ORDER BY wm.created_at"), {"w": workspace_id})).mappings().all()
    return list(rows)


@router.post("/workspaces/{workspace_id}/members/by-email", status_code=201)
async def add_member_by_email(workspace_id: str, body: MemberByEmail, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(workspace_id, p, db, {"owner", "admin"})
    target = (await db.execute(text("SELECT id,email FROM auth.users WHERE lower(email)=lower(:email) LIMIT 1"), {"email": str(body.email)})).mappings().first()
    if not target:
        raise HTTPException(404, "No DocuQuery account exists for this email yet. Ask the user to sign up first, then add them again.")
    target_id = str(target["id"])
    existing_role = (await db.execute(text("SELECT role FROM workspace_members WHERE workspace_id=:w AND user_id=:u"), {"w": workspace_id, "u": target_id})).scalar_one_or_none()
    if existing_role == "owner":
        raise HTTPException(409, "The workspace owner role cannot be changed from this action")
    await db.execute(text("INSERT INTO profiles(id,email) VALUES(:u,:e) ON CONFLICT(id) DO UPDATE SET email=COALESCE(EXCLUDED.email,profiles.email)"), {"u": target_id, "e": target["email"]})
    await db.execute(text("""
      INSERT INTO workspace_members(workspace_id,user_id,role,status) VALUES(:w,:u,:r,'active')
      ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='active'
    """), {"w": workspace_id, "u": target_id, "r": body.role})
    await write_audit(db, workspace_id=workspace_id, actor_user_id=p.user_id, action="workspace.member_upserted", resource_type="user", resource_id=target_id, request_id=request.state.request_id, ip=request.client.host if request.client else None, metadata={"role": body.role, "email": str(body.email)})
    await db.commit()
    return {"user_id": target_id, "email": target["email"], "role": body.role, "status": "active"}


@router.put("/workspaces/{workspace_id}/members")
async def upsert_member(workspace_id: str, body: MemberUpsert, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(workspace_id, p, db, {"owner", "admin"})
    target = (await db.execute(text("SELECT id,email FROM auth.users WHERE id=:u"), {"u": body.user_id})).mappings().first()
    if not target:
        raise HTTPException(404, "Supabase user not found")
    existing_role = (await db.execute(text("SELECT role FROM workspace_members WHERE workspace_id=:w AND user_id=:u"), {"w": workspace_id, "u": body.user_id})).scalar_one_or_none()
    if existing_role == "owner":
        raise HTTPException(409, "Owner role cannot be changed from this action")
    await db.execute(text("INSERT INTO profiles(id,email) VALUES(:u,:e) ON CONFLICT(id) DO UPDATE SET email=COALESCE(EXCLUDED.email,profiles.email)"), {"u": body.user_id, "e": target["email"]})
    await db.execute(text("""
      INSERT INTO workspace_members(workspace_id,user_id,role,status) VALUES(:w,:u,:r,'active')
      ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='active'
    """), {"w": workspace_id, "u": body.user_id, "r": body.role})
    await write_audit(db, workspace_id=workspace_id, actor_user_id=p.user_id, action="workspace.member_upserted", resource_type="user", resource_id=body.user_id, request_id=request.state.request_id, ip=request.client.host if request.client else None, metadata={"role": body.role})
    await db.commit()
    return {"user_id": body.user_id, "email": target["email"], "role": body.role, "status": "active"}


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member(workspace_id: str, user_id: str, request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(workspace_id, p, db, {"owner", "admin"})
    role = (await db.execute(text("SELECT role FROM workspace_members WHERE workspace_id=:w AND user_id=:u"), {"w": workspace_id, "u": user_id})).scalar_one_or_none()
    if role == "owner":
        raise HTTPException(409, "Owner cannot be removed")
    await db.execute(text("UPDATE workspace_members SET status='inactive' WHERE workspace_id=:w AND user_id=:u"), {"w": workspace_id, "u": user_id})
    await write_audit(db, workspace_id=workspace_id, actor_user_id=p.user_id, action="workspace.member_removed", resource_type="user", resource_id=user_id, request_id=request.state.request_id, ip=request.client.host if request.client else None)
    await db.commit()
