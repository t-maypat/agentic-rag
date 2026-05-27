import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rank_bm25 import BM25Okapi

from app.models import SourceChunk


@dataclass(frozen=True)
class LexicalChunk:
    chunk_id: str
    title: str | None
    source: str | None
    text: str


def _tokenize(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


def _load_chunks(index_path: Path) -> list[LexicalChunk]:
    if not index_path.exists():
        return []

    chunks: list[LexicalChunk] = []
    with index_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            chunks.append(
                LexicalChunk(
                    chunk_id=payload["chunk_id"],
                    title=payload.get("title"),
                    source=payload.get("source"),
                    text=payload.get("text", ""),
                )
            )

    return chunks


def upsert_chunks(index_path: Path, chunks: Iterable[LexicalChunk]) -> None:
    existing = {chunk.chunk_id: chunk for chunk in _load_chunks(index_path)}
    for chunk in chunks:
        existing[chunk.chunk_id] = chunk

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as handle:
        for chunk in existing.values():
            payload = {
                "chunk_id": chunk.chunk_id,
                "title": chunk.title,
                "source": chunk.source,
                "text": chunk.text,
            }
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def search(index_path: Path, query: str, top_k: int) -> list[SourceChunk]:
    chunks = _load_chunks(index_path)
    if not chunks:
        return []

    tokenized = [_tokenize(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(_tokenize(query))
    max_score = max(scores) if scores.any() else 1.0

    scored = list(zip(chunks, scores, strict=False))
    scored.sort(key=lambda item: item[1], reverse=True)

    results: list[SourceChunk] = []
    for chunk, score in scored[:top_k]:
        results.append(
            SourceChunk(
                chunk_id=chunk.chunk_id,
                score=float(score) / float(max_score or 1.0),
                title=chunk.title,
                source=chunk.source,
                text=chunk.text,
            )
        )

    return results
