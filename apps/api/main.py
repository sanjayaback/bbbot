from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apps.api.middleware import request_id_middleware
from apps.api.routers import health, workspaces, documents, chat, configuration, settings as settings_router, activity, maintenance

app=FastAPI(title="DocuQuery API",version="1.1.0",docs_url="/api/docs",openapi_url="/api/openapi.json")
app.middleware("http")(request_id_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000","http://localhost:8080","http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
    allow_headers=["authorization","content-type","x-request-id"],
)
app.include_router(health.router)
app.include_router(configuration.router)
app.include_router(workspaces.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(settings_router.router)
app.include_router(activity.router)
app.include_router(maintenance.router)

frontend=Path(__file__).resolve().parents[2]/"frontend"
if frontend.exists():
    app.mount("/",StaticFiles(directory=str(frontend),html=True),name="frontend")
