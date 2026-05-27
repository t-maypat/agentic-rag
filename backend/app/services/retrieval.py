from pathlib import Path

from app.core.config import settings
from app.models import SourceChunk
from app.services.embeddings import embedding_service
from app.services.lexical_index import search as lexical_search
from app.services.pinecone_client import pinecone_index


def _normalize_scores(chunks: list[SourceChunk]) -> list[SourceChunk]:
    if not chunks:
        return []

    max_score = max(chunk.score for chunk in chunks) or 1.0
    normalized: list[SourceChunk] = []
    for chunk in chunks:
        normalized.append(
            SourceChunk(
                chunk_id=chunk.chunk_id,
                score=chunk.score / max_score,
                title=chunk.title,
        vector_lookup = {chunk.chunk_id: chunk for chunk in vector_chunks}
        lexical_lookup = {chunk.chunk_id: chunk for chunk in lexical_chunks}
        combined: list[SourceChunk] = []
                source=metadata.get("source"),
        for chunk_id in set(vector_lookup) | set(lexical_lookup):
            vector_chunk = vector_lookup.get(chunk_id)
            lexical_chunk = lexical_lookup.get(chunk_id)
            vector_score = vector_chunk.score if vector_chunk else 0.0
            lexical_score = lexical_chunk.score if lexical_chunk else 0.0
            hybrid_score = (alpha * vector_score) + ((1.0 - alpha) * lexical_score)
            base = vector_chunk or lexical_chunk


                    chunk_id=chunk_id,
    vector_chunks: list[SourceChunk],
                    title=base.title if base else None,
                    source=base.source if base else None,
                    text=base.text if base else "",
) -> list[SourceChunk]:
    merged: dict[str, SourceChunk] = {}

    for chunk in vector_chunks:
        merged[chunk.chunk_id] = chunk

    for chunk in lexical_chunks:
        if chunk.chunk_id in merged:
            existing = merged[chunk.chunk_id]
            merged[chunk.chunk_id] = SourceChunk(
                chunk_id=existing.chunk_id,
                score=existing.score,
                title=existing.title or chunk.title,
                source=existing.source or chunk.source,
                text=existing.text or chunk.text,
            )
        else:
            merged[chunk.chunk_id] = chunk

    combined: list[SourceChunk] = []
    lexical_scores = {chunk.chunk_id: chunk.score for chunk in lexical_chunks}

    for chunk in merged.values():
        lexical_score = lexical_scores.get(chunk.chunk_id, 0.0)
        hybrid_score = (alpha * chunk.score) + ((1.0 - alpha) * lexical_score)
        combined.append(
            SourceChunk(
                chunk_id=chunk.chunk_id,
                score=hybrid_score,
                title=chunk.title,
                source=chunk.source,
                text=chunk.text,
            )
        )

    combined.sort(key=lambda item: item.score, reverse=True)
    return combined[:top_k]


def retrieve_chunks(query: str, top_k: int) -> list[SourceChunk]:
    vector_chunks = _retrieve_vector_chunks(query, top_k)

    if not settings.hybrid_search_enabled:
        return vector_chunks

    lexical_chunks = lexical_search(Path(settings.lexical_index_path), query, settings.bm25_k)
    return _merge_chunks(vector_chunks, lexical_chunks, settings.hybrid_alpha, top_k)
