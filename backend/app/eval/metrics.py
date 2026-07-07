"""Pure ranking metrics for the retrieval eval (REVAMP_PLAN §8.2).

Binary relevance: a ranked list of chunk ids is scored against a set of relevant
ids. No network, no SDK, no numpy — trivially unit-testable and deterministic.
"""

import math
from collections.abc import Iterable, Sequence


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    hits = sum(1 for chunk_id in ranked[:k] if chunk_id in relevant_set)
    return hits / len(relevant_set)


def reciprocal_rank_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    for position, chunk_id in enumerate(ranked[:k], start=1):
        if chunk_id in relevant_set:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    dcg = 0.0
    for position, chunk_id in enumerate(ranked[:k], start=1):
        if chunk_id in relevant_set:
            dcg += 1.0 / math.log2(position + 1)
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0
