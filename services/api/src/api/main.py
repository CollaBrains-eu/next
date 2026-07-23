import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api import tools as _tools  # noqa: F401 - import side effect: registers built-in tools (ADR 0021)
from api.activity_router import router as activity_router
from api.admin_router import router as admin_router
from api.appointments import router as appointments_router
from api.auth import router as auth_router
from api.cases_router import router as cases_router
from api.categories_router import router as categories_router
from api.chat import router as chat_router
from api.config import settings
from api.dashboard_router import router as dashboard_router
from api.db import engine
from api.decisions import router as decisions_router
from api.documents import router as documents_router, search_router
from api.entities import router as entities_router
from api.facts_router import router as facts_router
from api.feedback_router import router as feedback_router
from api.learning_router import router as learning_router
from api.legal import router as legal_router
from api.logging_config import configure_logging, log_request, request_id_var
from api.manager_router import router as manager_router
from api.mcp_router import router as mcp_router
from api.memories import router as memories_router
from api.onboarding_router import router as onboarding_router
from api.organizations_router import router as organizations_router
from api.plans import router as plans_router
from api.preferences_router import router as preferences_router
from api.residencies_router import router as residencies_router
from api.sharing_router import router as sharing_router
from api.tasks import router as tasks_router
from api.tools_router import router as tools_router
from api.users_router import router as users_router
from api.vehicles_router import router as vehicles_router
from api.webauthn_router import router as webauthn_router
from api.workspace_router import router as workspace_router

configure_logging()
logger = logging.getLogger("api.request")

app = FastAPI(title="CollaBrains API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    # Honor an incoming X-Request-ID (a caller that already has one -- e.g.
    # a future upstream proxy hop, or a client retry correlating attempts)
    # rather than always minting a fresh one.
    incoming_id = request.headers.get("x-request-id")
    request_id = incoming_id if incoming_id else str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    log_request(logger, method=request.method, path=request.url.path, status_code=response.status_code, duration_ms=duration_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full traceback goes to the (structured, request-ID-tagged) log for
    # debugging; the client gets a generic message, not internals -- same
    # privacy-conscious default this project applies to Sentry (ADR 0070).
    logger.error("unhandled_exception", exc_info=exc, extra={"path": request.url.path, "method": request.method})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(categories_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(feedback_router)
app.include_router(legal_router)
app.include_router(tasks_router)
app.include_router(entities_router)
app.include_router(facts_router)
app.include_router(memories_router)
app.include_router(plans_router)
app.include_router(tools_router)
app.include_router(mcp_router)
app.include_router(decisions_router)
app.include_router(manager_router)
app.include_router(preferences_router)
app.include_router(organizations_router)
app.include_router(learning_router)
app.include_router(vehicles_router)
app.include_router(residencies_router)
app.include_router(webauthn_router)
app.include_router(onboarding_router)
app.include_router(appointments_router)
app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(workspace_router)
app.include_router(activity_router)
app.include_router(sharing_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
