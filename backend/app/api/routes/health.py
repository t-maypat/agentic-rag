from fastapi import APIRouter

from app.core.config import settings
from app.retrieval.index import chunk_count, corpus_version

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "corpus_version": corpus_version(),
        "chunks": chunk_count(),
        "web_tool": bool(settings.tavily_api_key),
        "tracing": False,
    }
