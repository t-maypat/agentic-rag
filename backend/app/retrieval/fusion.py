"""Pure score-fusion logic for hybrid (dense + BM25) retrieval.

All functions are side-effect free and operate on ``SourceChunk`` domain objects,
making the normalization / alpha-weighting / dedup behavior unit-testable without
any network or SDK dependency.
"""

from app.models import SourceChunk


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Scale scores to [0, 1] by dividing by the max (top score maps to ~1.0)."""
    if not scores:
        return {}
    max_score = max(scores.values()) or 1.0
    return {chunk_id: score / max_score for chunk_id, score in scores.items()}


def fuse(
    dense_chunks: list[SourceChunk],
    lexical_chunks: list[SourceChunk],
    alpha: float,
    top_k: int,
) -> list[SourceChunk]:
    """Weighted fusion of dense and lexical candidates, deduped by chunk id.

    ``hybrid = alpha * dense_norm + (1 - alpha) * bm25_norm``. Dense chunks are
    expected to carry ``dense_score_norm``; lexical chunks carry ``bm25_score_norm``.
    Metadata is merged (dense wins) so a chunk found by only one retriever keeps
    whatever fields are available.
    """
    lexical_map = {chunk.chunk_id: chunk for chunk in lexical_chunks}
    merged: dict[str, SourceChunk] = {}

    for chunk in dense_chunks:
        merged[chunk.chunk_id] = chunk
    for chunk in lexical_chunks:
        merged.setdefault(chunk.chunk_id, chunk)

    combined: list[SourceChunk] = []
    for chunk_id, chunk in merged.items():
        lexical = lexical_map.get(chunk_id)
        dense_norm = chunk.dense_score_norm or 0.0
        bm25_norm = (lexical.bm25_score_norm if lexical else chunk.bm25_score_norm) or 0.0
        hybrid_score = (alpha * dense_norm) + ((1.0 - alpha) * bm25_norm)
        combined.append(
            SourceChunk(
                chunk_id=chunk_id,
                score=hybrid_score,
                dense_score=chunk.dense_score,
                dense_score_norm=dense_norm,
                bm25_score=(lexical.bm25_score if lexical else chunk.bm25_score),
                bm25_score_norm=bm25_norm,
                doc_id=chunk.doc_id or (lexical.doc_id if lexical else None),
                title=chunk.title or (lexical.title if lexical else None),
                section=chunk.section or (lexical.section if lexical else None),
                source=chunk.source or (lexical.source if lexical else None),
                authors=chunk.authors or (lexical.authors if lexical else None),
                year=chunk.year or (lexical.year if lexical else None),
                source_type=chunk.source_type or (lexical.source_type if lexical else None),
                url=chunk.url or (lexical.url if lexical else None),
                text=chunk.text or (lexical.text if lexical else ""),
            )
        )

    combined.sort(key=lambda item: item.score, reverse=True)
    return combined[:top_k]
