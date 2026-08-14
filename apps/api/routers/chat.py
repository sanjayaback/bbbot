import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.db import get_db
from apps.api.schemas import AskRequest, ChatSessionCreate
from apps.api.security import Principal, current_principal, require_workspace_role
from packages.ai.credentials import resolve_gemini_key
from packages.ai.factory import create_embedder, create_llm
from apps.api.config import settings
from packages.retrieval.context import build_context
from packages.retrieval.hybrid import hybrid_retrieve
from packages.security.audit import write_audit
from packages.security.quota import ensure_question_quota
from packages.security.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", status_code=201)
async def create_session(body: ChatSessionCreate, request:Request, principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    await require_workspace_role(body.workspace_id,principal,db,{"owner", "admin", "editor", "viewer"})
    if body.knowledge_base_ids:
        count=(await db.execute(text("SELECT count(*) FROM knowledge_bases WHERE workspace_id=:w AND id=ANY(CAST(:ids AS uuid[]))"),{"w":body.workspace_id,"ids":body.knowledge_base_ids})).scalar_one()
        if count != len(set(body.knowledge_base_ids)): raise HTTPException(400,"One or more knowledge bases are invalid")
    if body.document_ids:
        count=(await db.execute(text("SELECT count(*) FROM documents WHERE workspace_id=:w AND archived_at IS NULL AND id=ANY(CAST(:ids AS uuid[]))"),{"w":body.workspace_id,"ids":body.document_ids})).scalar_one()
        if count != len(set(body.document_ids)): raise HTTPException(400,"One or more documents are invalid")

    session_id = str(uuid.uuid4())
    await db.execute(text("INSERT INTO chat_sessions(id,workspace_id,user_id,title) VALUES(:id,:w,:u,:t)"),{"id": session_id, "w": body.workspace_id, "u": principal.user_id, "t": body.title or "New chat"})
    for source_type, ids in (("knowledge_base", body.knowledge_base_ids), ("document", body.document_ids)):
        for source_id in ids:
            await db.execute(text("INSERT INTO chat_session_sources(id,session_id,source_type,source_id) VALUES(:id,:s,:t,:x)"),{"id":str(uuid.uuid4()),"s":session_id,"t":source_type,"x":source_id})
    await write_audit(db,workspace_id=body.workspace_id,actor_user_id=principal.user_id,action="chat.created",resource_type="chat_session",resource_id=session_id,request_id=request.state.request_id,ip=request.client.host if request.client else None)
    await db.commit()
    return {"id": session_id}


@router.get("/sessions")
async def list_sessions(workspace_id:str,principal:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    await require_workspace_role(workspace_id,principal,db,{"owner","admin","editor","viewer"})
    rows=(await db.execute(text("""
      SELECT s.id,s.title,s.created_at,(SELECT count(*) FROM messages m WHERE m.session_id=s.id) AS message_count
      FROM chat_sessions s WHERE s.workspace_id=:w AND s.user_id=:u ORDER BY s.created_at DESC
    """),{"w":workspace_id,"u":principal.user_id})).mappings().all()
    return list(rows)


@router.get("/sessions/{session_id}")
async def session_detail(session_id:str,principal:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    session=(await db.execute(text("SELECT id,workspace_id,title,created_at FROM chat_sessions WHERE id=:s AND user_id=:u"),{"s":session_id,"u":principal.user_id})).mappings().first()
    if not session: raise HTTPException(404,"Session not found")
    await require_workspace_role(str(session['workspace_id']),principal,db,{"owner","admin","editor","viewer"})
    messages=(await db.execute(text("""
      SELECT m.id,m.role,m.content,m.status,m.created_at,
        COALESCE((SELECT jsonb_agg(jsonb_build_object('chunk_id',c.id,'document_id',d.id,'document',d.name,'page',p.page_number,'section',p.section_title) ORDER BY mc.citation_order)
          FROM message_citations mc JOIN chunks c ON c.id=mc.chunk_id JOIN document_versions v ON v.id=c.document_version_id JOIN documents d ON d.id=v.document_id LEFT JOIN document_pages p ON p.id=c.page_id WHERE mc.message_id=m.id),'[]'::jsonb) AS citations
      FROM messages m WHERE m.session_id=:s ORDER BY m.created_at
    """),{"s":session_id})).mappings().all()
    sources=(await db.execute(text("SELECT source_type,source_id FROM chat_session_sources WHERE session_id=:s"),{"s":session_id})).mappings().all()
    return {"session":dict(session),"sources":list(sources),"messages":list(messages)}


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id:str,principal:Principal=Depends(current_principal),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(text("SELECT workspace_id FROM chat_sessions WHERE id=:s AND user_id=:u"),{"s":session_id,"u":principal.user_id})).mappings().first()
    if not row: raise HTTPException(404,"Session not found")
    await db.execute(text("DELETE FROM chat_sessions WHERE id=:s"),{"s":session_id})
    await db.commit()


@router.post("/sessions/{session_id}/ask")
async def ask(session_id: str, body: AskRequest, request:Request, principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    session=(await db.execute(text("SELECT id,workspace_id FROM chat_sessions WHERE id=:s AND user_id=:u"),{"s": session_id, "u": principal.user_id})).mappings().first()
    if not session: raise HTTPException(404, "Session not found")
    workspace_id=str(session["workspace_id"])
    await require_workspace_role(workspace_id,principal,db,{"owner", "admin", "editor", "viewer"})
    await enforce_rate_limit(principal.user_id,"ask")
    await ensure_question_quota(db,workspace_id)

    needs_gemini = (
        settings.embedding_provider.lower() == "gemini"
        or settings.chat_provider.lower() == "gemini"
    )
    api_key = await resolve_gemini_key(db, workspace_id) if needs_gemini else None

    embedder = create_embedder(api_key)
    embed_query = getattr(embedder, "embed_query", embedder.embed)
    query_embedding = await embed_query(body.question)
    if len(query_embedding) != settings.embedding_dimension:
        raise HTTPException(503, "Embedding provider returned an incompatible vector dimension")

    sources=(await db.execute(text("SELECT source_type,source_id FROM chat_session_sources WHERE session_id=:s"),{"s": session_id})).mappings().all()
    embed_provider = getattr(embedder, "provider", settings.embedding_provider.lower())
    embed_model = getattr(embedder, "model", None)
    chunks = await hybrid_retrieve(
        db,
        workspace_id,
        query_embedding,
        body.question,
        list(sources),
        limit=8,
        embedding_provider=embed_provider,
        embedding_model=embed_model,
    )
    context, citations = build_context(chunks)

    user_message_id=str(uuid.uuid4())
    await db.execute(text("INSERT INTO messages(id,session_id,user_id,role,content,status) VALUES(:id,:s,:u,'user',:c,'completed')"),{"id":user_message_id,"s":session_id,"u":principal.user_id,"c":body.question})
    assistant_message_id = str(uuid.uuid4())
    await db.execute(text("INSERT INTO messages(id,session_id,user_id,role,content,status) VALUES(:id,:s,:u,'assistant','','generating')"),{"id": assistant_message_id, "s": session_id, "u": principal.user_id})

    llm = create_llm(api_key)
    provider = getattr(llm, "provider", settings.chat_provider.lower())
    model = getattr(llm, "model", "unknown")
    usage_id=str(uuid.uuid4())
    await db.execute(text("INSERT INTO usage_events(id,workspace_id,user_id,operation,provider,model,input_tokens) VALUES(:id,:w,:u,'chat_question',:p,:m,:t)"),{"id":usage_id,"w":workspace_id,"u":principal.user_id,"p":provider,"m":model,"t":max(1,(len(body.question)+len(context))//4)})
    await write_audit(db,workspace_id=workspace_id,actor_user_id=principal.user_id,action="chat.question",resource_type="chat_session",resource_id=session_id,request_id=request.state.request_id,ip=request.client.host if request.client else None,metadata={"embedding_provider":embed_provider,"embedding_model":embed_model,"chat_provider":settings.chat_provider})
    await db.commit()

    async def stream():
        parts: list[str] = []
        try:
            async for token in llm.stream_answer(body.question, context):
                parts.append(token)
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
            answer = "".join(parts)
            await db.execute(text("UPDATE messages SET content=:c,status='completed',completed_at=now() WHERE id=:id"),{"c":answer,"id":assistant_message_id})
            for order,citation in enumerate(citations,1):
                await db.execute(text("INSERT INTO message_citations(id,message_id,chunk_id,citation_order) VALUES(:id,:m,:c,:o)"),{"id":str(uuid.uuid4()),"m":assistant_message_id,"c":citation["chunk_id"],"o":order})
            await db.execute(text("UPDATE usage_events SET output_tokens=:t WHERE id=:id"),{"t":max(1,len(answer)//4),"id":usage_id})
            await db.commit()
            yield f"data: {json.dumps({'type':'citations','items':citations,'message_id':assistant_message_id,'mode':settings.app_mode,'chat_provider':settings.chat_provider})}\n\n"
            yield 'data: {"type":"done"}\n\n'
        except Exception as exc:
            await db.rollback()
            await db.execute(text("UPDATE messages SET status='failed' WHERE id=:id"),{"id":assistant_message_id})
            await db.commit()
            yield f"data: {json.dumps({'type':'error','message':f'Answer generation failed: {str(exc)[:240]}'})}\n\n"

    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
