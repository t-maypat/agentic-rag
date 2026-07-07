"""Offline tests for the eval harness (metrics, local store, drift guard).

No committed fixtures, no network: a tiny synthetic embedding matrix exercises the
same LocalNumpyStore + BM25 + fusion path the CI retrieval eval uses.
"""

import json

import numpy as np
import pytest

from app.adapters.vectorstore import LocalNumpyStore
from app.eval import metrics
from app.eval.datasets import corpus_version, questions_signature
from app.eval.fixtures import FixtureDriftError, assert_fixtures_current
from app.eval.harness import evaluate_retrieval, hybrid_rank
from app.retrieval.bm25 import Bm25Index, LexicalChunk


def test_recall_at_k():
    ranked = ["a", "b", "c", "d"]
    assert metrics.recall_at_k(ranked, {"b", "d"}, 5) == 1.0
    assert metrics.recall_at_k(ranked, {"b", "d"}, 2) == 0.5
    assert metrics.recall_at_k(ranked, {"z"}, 5) == 0.0
    assert metrics.recall_at_k(ranked, set(), 5) == 0.0


def test_reciprocal_rank_at_k():
    ranked = ["a", "b", "c"]
    assert metrics.reciprocal_rank_at_k(ranked, {"b"}, 10) == 0.5
    assert metrics.reciprocal_rank_at_k(ranked, {"a"}, 10) == 1.0
    assert metrics.reciprocal_rank_at_k(ranked, {"c"}, 2) == 0.0  # beyond cutoff


def test_ndcg_at_k_orders_matter():
    perfect = metrics.ndcg_at_k(["a", "b", "x"], {"a", "b"}, 10)
    worse = metrics.ndcg_at_k(["x", "a", "b"], {"a", "b"}, 10)
    assert perfect == pytest.approx(1.0)
    assert worse < perfect


def _store() -> LocalNumpyStore:
    # Three orthogonal-ish unit vectors so cosine ranking is unambiguous.
    ids = ["doc-a:0", "doc-b:0", "doc-c:0"]
    vectors = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    metadata = {cid: {"chunk_id": cid, "title": cid, "text": f"text {cid}"} for cid in ids}
    return LocalNumpyStore(ids, vectors, metadata)


def test_local_store_ranks_by_cosine_and_normalizes():
    store = _store()
    results = store.query([0.9, 0.1, 0.0], top_k=3)
    assert [c.chunk_id for c in results] == ["doc-a:0", "doc-b:0", "doc-c:0"]
    assert results[0].dense_score_norm == pytest.approx(1.0)  # top maps to 1.0
    assert results[0].score == pytest.approx(1.0)


def test_hybrid_rank_combines_dense_and_lexical():
    store = _store()
    bm25 = Bm25Index(
        [
            LexicalChunk(
                chunk_id=cid,
                doc_id=None,
                title=cid,
                section=None,
                source=None,
                authors=None,
                year=None,
                source_type=None,
                url=None,
                text=f"text {cid}",
            )
            for cid in ["doc-a:0", "doc-b:0", "doc-c:0"]
        ]
    )
    ranked = hybrid_rank(store, bm25, [1.0, 0.0, 0.0], "text doc-a:0", alpha=0.6)
    assert ranked[0] == "doc-a:0"


def test_evaluate_retrieval_separates_unanswerable():
    store = _store()
    bm25 = Bm25Index([])  # dense-only is enough to rank the synthetic vectors
    items = [
        {
            "qid": "q1",
            "question": "find a",
            "relevant_chunk_ids": ["doc-a:0"],
            "category": "definitional",
        },
        {
            "qid": "q2",
            "question": "off topic",
            "relevant_chunk_ids": [],
            "category": "unanswerable",
        },
    ]
    query_vectors = {
        "q1": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "q2": np.array([0.3, 0.3, 0.3], dtype=np.float32),
    }
    report = evaluate_retrieval(items, store, bm25, query_vectors, alpha=1.0)
    assert report["n_answerable"] == 1
    assert report["n_unanswerable"] == 1
    assert report["overall"]["recall@5"] == pytest.approx(1.0)
    assert report["unanswerable"][0]["top_dense_cosine"] is not None


def test_drift_guard_detects_stale_fixtures(tmp_path):
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(json.dumps({"chunk_id": "x:0", "text": "hello"}) + "\n", encoding="utf-8")
    questions = ["what is x?"]

    corpus_npz = tmp_path / "corpus.npz"
    query_npz = tmp_path / "query.npz"
    good_meta = {"corpus_version": corpus_version(chunks)}
    np.savez(
        corpus_npz,
        ids=np.array(["x:0"], dtype=object),
        vectors=np.zeros((1, 2)),
        meta=json.dumps(good_meta),
    )
    np.savez(
        query_npz,
        qids=np.array(["q1"], dtype=object),
        vectors=np.zeros((1, 2)),
        meta=json.dumps(
            {"corpus_version": corpus_version(chunks), "questions_signature": "deadbeef"}
        ),
    )
    with pytest.raises(FixtureDriftError):
        assert_fixtures_current(
            corpus_npz=corpus_npz,
            query_npz=query_npz,
            chunks_path=chunks,
            retrieval_questions=questions,
        )

    # Fix the signature → guard passes.
    np.savez(
        query_npz,
        qids=np.array(["q1"], dtype=object),
        vectors=np.zeros((1, 2)),
        meta=json.dumps(
            {
                "corpus_version": corpus_version(chunks),
                "questions_signature": questions_signature(questions),
            }
        ),
    )
    assert_fixtures_current(
        corpus_npz=corpus_npz,
        query_npz=query_npz,
        chunks_path=chunks,
        retrieval_questions=questions,
    )
