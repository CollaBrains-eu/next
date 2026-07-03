from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api import tools as _tools  # noqa: F401 - import side effect: registers built-in tools (ADR 0021)
from api.auth import router as auth_router
from api.chat import router as chat_router
from api.db import engine
from api.decisions import router as decisions_router
from api.documents import router as documents_router, search_router
from api.entities import router as entities_router
from api.legal import router as legal_router
from api.mcp_router import router as mcp_router
from api.memories import router as memories_router
from api.plans import router as plans_router
from api.tasks import router as tasks_router
from api.tools_router import router as tools_router

app = FastAPI(title="CollaBrains API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(legal_router)
app.include_router(tasks_router)
app.include_router(entities_router)
app.include_router(memories_router)
app.include_router(plans_router)
app.include_router(tools_router)
app.include_router(mcp_router)
app.include_router(decisions_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
