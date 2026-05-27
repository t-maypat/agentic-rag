from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.models import SourceChunk
from app.services.embeddings import embedding_service
from app.services.lexical_index import search as lexical_search
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


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values()) or 1.0
    return {chunk_id: score / max_score for chunk_id, score in scores.items()}


def _retrieve_vector_chunks(query: str, top_k: int) -> list[SourceChunk]:
    embedding = embedding_service.embed_query(query)
    result = pinecone_index.query(vector=embedding, top_k=top_k, include_metadata=True)
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

    normalized = _normalize_scores(raw_scores)
    normalized_chunks: list[SourceChunk] = []
    for chunk in raw_chunks:
        norm_score = normalized.get(chunk.chunk_id, 0.0)
        normalized_chunks.append(
            SourceChunk(
                chunk_id=chunk.chunk_id,
                score=norm_score,
                dense_score=chunk.dense_score,
                dense_score_norm=norm_score,
                doc_id=chunk.doc_id,
                title=chunk.title,
                section=chunk.section,
                source=chunk.source,
                authors=chunk.authors,
                year=chunk.year,
                source_type=chunk.source_type,
                url=chunk.url,
                text=chunk.text,
            )
        )

    return normalized_chunks


def _merge_chunks(
    vector_chunks: list[SourceChunk],
    lexical_chunks: list[SourceChunk],
    alpha: float,
    top_k: int,
) -> list[SourceChunk]:
    merged: dict[str, SourceChunk] = {}
    lexical_map = {chunk.chunk_id: chunk for chunk in lexical_chunks}

    for chunk in vector_chunks:
        merged[chunk.chunk_id] = chunk

    for chunk in lexical_chunks:
        if chunk.chunk_id in merged:
            existing = merged[chunk.chunk_id]
            merged[chunk.chunk_id] = SourceChunk(
                chunk_id=existing.chunk_id,
                score=existing.score,
                dense_score=existing.dense_score,
                dense_score_norm=existing.dense_score_norm,
                bm25_score=chunk.bm25_score,
                bm25_score_norm=chunk.bm25_score_norm,
                doc_id=existing.doc_id or chunk.doc_id,
                title=existing.title or chunk.title,
                section=existing.section or chunk.section,
                source=existing.source or chunk.source,
                authors=existing.authors or chunk.authors,
                year=existing.year or chunk.year,
                source_type=existing.source_type or chunk.source_type,
                url=existing.url or chunk.url,
                text=existing.text or chunk.text,
            )
        else:
            merged[chunk.chunk_id] = chunk

    combined: list[SourceChunk] = []
    for chunk in merged.values():
        lexical = lexical_map.get(chunk.chunk_id)
        dense_norm = chunk.dense_score_norm or 0.0
        bm25_norm = lexical.bm25_score_norm if lexical else chunk.bm25_score_norm or 0.0
        hybrid_score = (alpha * dense_norm) + ((1.0 - alpha) * bm25_norm)
        combined.append(
            SourceChunk(
                chunk_id=chunk.chunk_id,
                score=hybrid_score,
                dense_score=chunk.dense_score,
                dense_score_norm=dense_norm,
                bm25_score=lexical.bm25_score if lexical else chunk.bm25_score,
                bm25_score_norm=bm25_norm,
                doc_id=chunk.doc_id,
                title=chunk.title,
                section=chunk.section,
                source=chunk.source,
                authors=chunk.authors,
                year=chunk.year,
                source_type=chunk.source_type,
                url=chunk.url,
                text=chunk.text,
            )
        )

    combined.sort(key=lambda item: item.score, reverse=True)
    return combined[:top_k]


def retrieve_chunks(query: str, top_k: int) -> RetrievalResult:
    vector_chunks = _retrieve_vector_chunks(query, top_k)

    if not settings.hybrid_search_enabled:
        diagnostics = RetrievalDiagnostics(
            dense_candidates=vector_chunks,
            lexical_candidates=[],
            fused_candidates=vector_chunks,
        )
        return RetrievalResult(chunks=vector_chunks, diagnostics=diagnostics)

    lexical_chunks = lexical_search(Path(settings.lexical_index_path), query, settings.bm25_k)
    fused = _merge_chunks(vector_chunks, lexical_chunks, settings.hybrid_alpha, top_k)
    diagnostics = RetrievalDiagnostics(
        dense_candidates=vector_chunks,
        lexical_candidates=lexical_chunks,
        fused_candidates=fused,
    )
    return RetrievalResult(chunks=fused, diagnostics=diagnostics)
