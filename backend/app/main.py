from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router
from app.core.config import settings
from app.retrieval.index import init_retrieval

app = FastAPI(title=settings.api_title, version=settings.api_version)


@app.on_event("startup")
async def startup() -> None:
    # Build the BM25 index + corpus version once from the committed chunk file.
    init_retrieval()


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

# New API surface (Phase 0: health only; /api/research lands in Phase 1).
app.include_router(health_router, prefix="/api")
# Legacy endpoint kept working until Phase 1 replaces it with /api/research.
app.include_router(query_router)
