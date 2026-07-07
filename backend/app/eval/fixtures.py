"""Committed embedding fixtures + drift guard (REVAMP_PLAN §8.2, §16).

``corpus_embeddings.npz`` and ``query_embeddings.npz`` are produced once with a
live key by ``scripts/build_eval_fixtures.py`` and committed (~a few MB). Each
carries metadata so the eval fails loudly — with regeneration instructions —
whenever the corpus or golden questions drift out of sync with the vectors.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.eval.datasets import corpus_version, questions_signature


class FixtureDriftError(RuntimeError):
    """Raised when committed fixtures no longer match the corpus/golden questions."""


def read_meta(npz_path: Path) -> dict[str, Any]:
    data = np.load(npz_path, allow_pickle=True)
    if "meta" not in data:
        return {}
    return json.loads(str(data["meta"]))


@dataclass(frozen=True)
class QueryEmbeddings:
    qids: list[str]
    vectors: np.ndarray  # (N, D) float32

    def by_qid(self) -> dict[str, np.ndarray]:
        return {qid: self.vectors[i] for i, qid in enumerate(self.qids)}


def load_query_embeddings(npz_path: Path) -> QueryEmbeddings:
    data = np.load(npz_path, allow_pickle=True)
    qids = [str(qid) for qid in data["qids"].tolist()]
    vectors = np.asarray(data["vectors"], dtype=np.float32)
    return QueryEmbeddings(qids=qids, vectors=vectors)


def assert_fixtures_current(
    *,
    corpus_npz: Path,
    query_npz: Path,
    chunks_path: Path,
    retrieval_questions: list[str],
) -> None:
    """Guard against stale fixtures. Raises :class:`FixtureDriftError` on mismatch."""
    expected_corpus = corpus_version(chunks_path)
    expected_questions = questions_signature(retrieval_questions)

    corpus_meta = read_meta(corpus_npz)
    query_meta = read_meta(query_npz)

    problems: list[str] = []
    if corpus_meta.get("corpus_version") != expected_corpus:
        problems.append(
            f"corpus_embeddings.npz corpus_version={corpus_meta.get('corpus_version')!r} "
            f"but chunks.jsonl is {expected_corpus!r}"
        )
    if query_meta.get("corpus_version") != expected_corpus:
        problems.append(
            f"query_embeddings.npz corpus_version={query_meta.get('corpus_version')!r} "
            f"but chunks.jsonl is {expected_corpus!r}"
        )
    if query_meta.get("questions_signature") != expected_questions:
        problems.append(
            f"query_embeddings.npz questions_signature={query_meta.get('questions_signature')!r} "
            f"but golden_retrieval.jsonl is {expected_questions!r}"
        )
    if problems:
        raise FixtureDriftError(
            "Eval fixtures are stale:\n  - "
            + "\n  - ".join(problems)
            + "\nRegenerate with: uv run python scripts/build_eval_fixtures.py"
        )
