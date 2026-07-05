"""Startup-built BM25 singleton and corpus-version bookkeeping.

Kept free of Pinecone/embedding imports so lightweight consumers (e.g. the health
endpoint) can read corpus metadata without touching the vector store.
"""

import hashlib
from pathlib import Path

from app.core.config import settings
from app.retrieval.bm25 import Bm25Index

# Repo root (…/backend/app/retrieval/index.py -> parents[3]) so data paths resolve
# regardless of the process working directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]

_bm25_index: Bm25Index | None = None
_corpus_version: str | None = None


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else _REPO_ROOT / path


def _hash_file(path: Path) -> str:
    if not path.exists():
        return "empty"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def init_retrieval() -> None:
    """Build the BM25 singleton and compute the corpus version. Call at startup."""
    global _bm25_index, _corpus_version
    path = _resolve(settings.chunks_path)
    _bm25_index = Bm25Index.from_path(path)
    _corpus_version = _hash_file(path)


def get_bm25_index() -> Bm25Index:
    if _bm25_index is None:
        init_retrieval()
    assert _bm25_index is not None
    return _bm25_index


def corpus_version() -> str:
    if _corpus_version is None:
        init_retrieval()
    assert _corpus_version is not None
    return _corpus_version


def chunk_count() -> int:
    return len(get_bm25_index())
