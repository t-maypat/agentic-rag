"""Hybrid retrieval service.

Thin impure layer that wires the dense (Pinecone) retriever and the BM25 index
(built once at startup from the committed ``data/index/chunks.jsonl``) into the
pure fusion logic in ``app.retrieval``.
"""

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.models import SourceChunk
from app.retrieval.fusion import fuse, normalize_scores
from app.retrieval.index import get_bm25_index
from app.services.embeddings import embedding_service
from app.services.pinecone_client import pinecone_index


@dataclass(frozen=True)
class RetrievalDiagnostics:
    dense_candidates: list[SourceChunk]
    lexical_candidates: list[SourceChunk]
    fused_candidates: list[SourceChunk]


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[SourceChunk]
    diagnostics: RetrievalDiagnostics


def _retrieve_vector_chunks(query: str, top_k: int) -> list[SourceChunk]:
    embedding = embedding_service.embed_query(query)
    result: Any = pinecone_index.query(vector=embedding, top_k=top_k, include_metadata=True)
    matches = getattr(result, "matches", None)
    if matches is None and isinstance(result, dict):
        matches = result.get("matches", [])
    if matches is None:
        matches = []

    raw_scores: dict[str, float] = {}
    raw_chunks: list[SourceChunk] = []
    for match in matches:
        if isinstance(match, dict):
            chunk_id = match.get("id", "")
            score = float(match.get("score") or 0.0)
            metadata = match.get("metadata") or {}
        else:
            chunk_id = getattr(match, "id", "")
            score = float(getattr(match, "score", 0.0) or 0.0)
            metadata = getattr(match, "metadata", None) or {}

        raw_scores[chunk_id] = score
        raw_chunks.append(
            SourceChunk(
                chunk_id=chunk_id,
                score=score,
                dense_score=score,
                doc_id=metadata.get("doc_id"),
                title=metadata.get("title"),
                section=metadata.get("section"),
                source=metadata.get("source"),
                authors=metadata.get("authors"),
                year=metadata.get("year"),
                source_type=metadata.get("source_type"),
                url=metadata.get("url"),
                text=metadata.get("text", ""),
            )
        )

    normalized = normalize_scores(raw_scores)
    for chunk in raw_chunks:
        norm = normalized.get(chunk.chunk_id, 0.0)
        chunk.score = norm
        chunk.dense_score_norm = norm
    return raw_chunks


def retrieve_chunks(query: str, top_k: int) -> RetrievalResult:
    vector_chunks = _retrieve_vector_chunks(query, top_k)
    lexical_chunks = get_bm25_index().search(query, top_k)
    fused = fuse(vector_chunks, lexical_chunks, settings.hybrid_alpha, top_k)
    diagnostics = RetrievalDiagnostics(
        dense_candidates=vector_chunks,
        lexical_candidates=lexical_chunks,
        fused_candidates=fused,
    )
    return RetrievalResult(chunks=fused, diagnostics=diagnostics)
