"""BM25 lexical retrieval over the committed chunk index.

The index is a JSONL file (``data/index/chunks.jsonl``) produced by
``scripts/build_chunks.py`` and committed to the repo, so the running server and
CI never depend on a prior ingest run against ephemeral disk. ``Bm25Index`` is a
pure object built once at startup (see the retrieval service singleton).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.models import SourceChunk


def tokenize(text: str) -> list[str]:
    """Lowercase whitespace tokenization (kept from the original lexical index)."""
    return [token for token in text.lower().split() if token]


@dataclass(frozen=True)
class LexicalChunk:
    chunk_id: str
    doc_id: str | None
    title: str | None
    section: str | None
    source: str | None
    authors: list[str] | None
    year: int | None
    source_type: str | None
    url: str | None
    text: str


def _chunk_from_payload(payload: dict) -> LexicalChunk:
    return LexicalChunk(
        chunk_id=payload["chunk_id"],
        doc_id=payload.get("doc_id"),
        title=payload.get("title"),
        section=payload.get("section"),
        source=payload.get("source"),
        authors=payload.get("authors"),
        year=payload.get("year"),
        source_type=payload.get("source_type"),
        url=payload.get("url"),
        text=payload.get("text", ""),
    )


def load_chunks(index_path: Path) -> list[LexicalChunk]:
    if not index_path.exists():
        return []
    chunks: list[LexicalChunk] = []
    with index_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                chunks.append(_chunk_from_payload(json.loads(line)))
    return chunks


class Bm25Index:
    """In-memory BM25 index. Immutable after construction."""

    def __init__(self, chunks: list[LexicalChunk]) -> None:
        self._chunks = chunks
        self._bm25 = BM25Okapi([tokenize(chunk.text) for chunk in chunks]) if chunks else None

    @classmethod
    def from_path(cls, index_path: Path) -> "Bm25Index":
        return cls(load_chunks(index_path))

    def __len__(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int) -> list[SourceChunk]:
        if not self._chunks or self._bm25 is None:
            return []

        scores = self._bm25.get_scores(tokenize(query))
        max_score = float(max(scores)) if len(scores) else 1.0
        max_score = max_score or 1.0

        scored = sorted(
            zip(self._chunks, scores, strict=True), key=lambda item: item[1], reverse=True
        )

        results: list[SourceChunk] = []
        for chunk, score in scored[:top_k]:
            norm = float(score) / max_score
            results.append(
                SourceChunk(
                    chunk_id=chunk.chunk_id,
                    score=norm,
                    bm25_score=float(score),
                    bm25_score_norm=norm,
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
        return results
