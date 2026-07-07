"""Vector-store port + adapters.

The server runtime retrieves dense candidates from Pinecone (see
``app.services.retrieval``). The CI/offline retrieval eval (REVAMP_PLAN §8.2) needs
the *same* hybrid pipeline without any network, so it swaps Pinecone for
:class:`LocalNumpyStore` — a cosine search over committed corpus embeddings that
returns the identical ``SourceChunk`` shape the fusion logic consumes.

``VectorStore.query`` returns candidates whose ``dense_score`` is the raw cosine
and whose ``dense_score_norm``/``score`` are max-normalized, mirroring
``_retrieve_vector_chunks`` so fusion behaves the same for both adapters.
"""

import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.models import SourceChunk
from app.retrieval.fusion import normalize_scores


class VectorStore(Protocol):
    def query(self, vector: list[float], top_k: int) -> list[SourceChunk]: ...


def _unit_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


class LocalNumpyStore:
    """Cosine search over an in-memory embedding matrix (used by CI evals only).

    Rows are unit-normalized at construction so a query dot-product equals cosine
    similarity, matching Pinecone's ``cosine`` metric.
    """

    def __init__(
        self,
        ids: list[str],
        vectors: np.ndarray,
        metadata: dict[str, dict[str, Any]],
    ) -> None:
        if len(ids) != vectors.shape[0]:
            raise ValueError("ids and vectors length mismatch")
        self._ids = ids
        self._matrix = _unit_rows(np.asarray(vectors, dtype=np.float32))
        self._metadata = metadata

    @classmethod
    def from_files(cls, embeddings_path: Path, chunks_path: Path) -> "LocalNumpyStore":
        data = np.load(embeddings_path, allow_pickle=True)
        ids = [str(chunk_id) for chunk_id in data["ids"].tolist()]
        vectors = np.asarray(data["vectors"], dtype=np.float32)

        metadata: dict[str, dict[str, Any]] = {}
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    payload = json.loads(line)
                    metadata[payload["chunk_id"]] = payload
        return cls(ids, vectors, metadata)

    def __len__(self) -> int:
        return len(self._ids)

    def query(self, vector: list[float], top_k: int) -> list[SourceChunk]:
        if not self._ids:
            return []
        query_vec = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(query_vec)) or 1.0
        sims = self._matrix @ (query_vec / norm)

        top_k = min(top_k, len(self._ids))
        order = np.argsort(-sims)[:top_k]
        raw_scores = {self._ids[i]: float(sims[i]) for i in order}
        normalized = normalize_scores(raw_scores)

        chunks: list[SourceChunk] = []
        for i in order:
            chunk_id = self._ids[i]
            meta = self._metadata.get(chunk_id, {})
            norm_score = normalized.get(chunk_id, 0.0)
            chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    score=norm_score,
                    dense_score=raw_scores[chunk_id],
                    dense_score_norm=norm_score,
                    doc_id=meta.get("doc_id"),
                    title=meta.get("title"),
                    section=meta.get("section"),
                    source=meta.get("source"),
                    authors=meta.get("authors"),
                    year=meta.get("year"),
                    source_type=meta.get("source_type"),
                    url=meta.get("url"),
                    text=meta.get("text", ""),
                )
            )
        return chunks
