from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes.health import router as health_router
from app.api.routes.research import router as research_router
from app.api.routes.threads import router as threads_router
from app.core.config import settings
from app.retrieval.index import init_retrieval

app = FastAPI(title=settings.api_title, version=settings.api_version)


@app.on_event("startup")
async def startup() -> None:
    # Build the BM25 index + corpus version once from the committed chunk file,
    # and compile the agent graph + checkpointer.
    init_retrieval()
    from app.agent.runtime import init_runtime

    init_runtime()


@app.on_event("shutdown")
async def shutdown() -> None:
    # Flush any buffered Langfuse events before the process exits (no-op if tracing off).
    from app import observability

    observability.flush()


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(threads_router, prefix="/api")
