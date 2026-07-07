"""Offline hybrid-retrieval harness + metric aggregation (REVAMP_PLAN §8.2).

Runs the *same* fusion pipeline the server uses (local dense + real BM25 +
``app.retrieval.fusion.fuse``) over precomputed query embeddings, then aggregates
recall@5/@10, MRR@10, and nDCG@10 overall and per category across the answerable
items only. Answerable = non-empty ``relevant_chunk_ids``.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np

from app.adapters.vectorstore import VectorStore
from app.eval import metrics
from app.retrieval.bm25 import Bm25Index
from app.retrieval.fusion import fuse

# Retrieve deeper than the metric cutoffs so recall@10 / nDCG@10 are well-defined
# even after fusion dedups the dense+lexical candidate pools.
CANDIDATE_K = 20


def hybrid_rank(
    store: VectorStore,
    bm25: Bm25Index,
    query_vector: Sequence[float],
    query_text: str,
    alpha: float,
    candidate_k: int = CANDIDATE_K,
) -> list[str]:
    """Return fused chunk ids ranked best-first for one query."""
    dense = store.query(list(query_vector), candidate_k)
    lexical = bm25.search(query_text, candidate_k)
    fused = fuse(dense, lexical, alpha, candidate_k)
    return [chunk.chunk_id for chunk in fused]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate_retrieval(
    items: list[dict[str, Any]],
    store: VectorStore,
    bm25: Bm25Index,
    query_vectors: dict[str, np.ndarray],
    alpha: float,
) -> dict[str, Any]:
    """Aggregate retrieval metrics; separate answerable gate items from unanswerable."""
    per_item: list[dict[str, Any]] = []
    by_category: dict[str, list[dict[str, float]]] = {}
    answerable_scores: list[dict[str, float]] = []
    unanswerable: list[dict[str, Any]] = []

    for item in items:
        qid = item["qid"]
        relevant = item.get("relevant_chunk_ids") or []
        vector = query_vectors[qid]

        if not relevant:
            # Unanswerable: report top raw dense cosine only (informational, ungated).
            dense = store.query(vector.tolist(), 1)
            top_cosine = dense[0].dense_score if dense else None
            unanswerable.append(
                {"qid": qid, "category": item.get("category"), "top_dense_cosine": top_cosine}
            )
            continue

        ranked = hybrid_rank(store, bm25, vector.tolist(), item["question"], alpha)
        scores = {
            "recall@5": metrics.recall_at_k(ranked, relevant, 5),
            "recall@10": metrics.recall_at_k(ranked, relevant, 10),
            "mrr@10": metrics.reciprocal_rank_at_k(ranked, relevant, 10),
            "ndcg@10": metrics.ndcg_at_k(ranked, relevant, 10),
        }
        answerable_scores.append(scores)
        category = item.get("category", "uncategorized")
        by_category.setdefault(category, []).append(scores)
        per_item.append({"qid": qid, "category": category, **scores})

    metric_names = ["recall@5", "recall@10", "mrr@10", "ndcg@10"]
    overall = {name: _mean([s[name] for s in answerable_scores]) for name in metric_names}
    category_summary = {
        category: {
            "n": len(scores),
            **{name: _mean([s[name] for s in scores]) for name in metric_names},
        }
        for category, scores in sorted(by_category.items())
    }

    return {
        "n_answerable": len(answerable_scores),
        "n_unanswerable": len(unanswerable),
        "overall": overall,
        "by_category": category_summary,
        "per_item": per_item,
        "unanswerable": unanswerable,
    }
