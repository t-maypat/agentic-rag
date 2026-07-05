from app.models import SourceChunk
from app.retrieval.fusion import fuse, normalize_scores


def test_normalize_scores_divides_by_max():
    normalized = normalize_scores({"a": 2.0, "b": 4.0, "c": 1.0})
    assert normalized["b"] == 1.0
    assert normalized["a"] == 0.5
    assert normalized["c"] == 0.25


def test_normalize_scores_empty():
    assert normalize_scores({}) == {}


def _dense(chunk_id: str, norm: float) -> SourceChunk:
    return SourceChunk(chunk_id=chunk_id, score=norm, dense_score_norm=norm, text=chunk_id)


def _lexical(chunk_id: str, norm: float) -> SourceChunk:
    return SourceChunk(chunk_id=chunk_id, score=norm, bm25_score_norm=norm, text=chunk_id)


def test_fuse_alpha_weighting():
    dense = [_dense("a", 1.0)]
    lexical = [_lexical("a", 0.5)]
    fused = fuse(dense, lexical, alpha=0.6, top_k=5)
    assert len(fused) == 1
    # 0.6 * 1.0 + 0.4 * 0.5 = 0.8
    assert abs(fused[0].score - 0.8) < 1e-9


def test_fuse_dedup_by_chunk_id():
    dense = [_dense("a", 1.0), _dense("b", 0.4)]
    lexical = [_lexical("a", 0.9), _lexical("c", 0.7)]
    fused = fuse(dense, lexical, alpha=0.5, top_k=10)
    ids = sorted(chunk.chunk_id for chunk in fused)
    assert ids == ["a", "b", "c"]  # 'a' appears once


def test_fuse_respects_top_k_and_sorts_desc():
    dense = [_dense("a", 0.2), _dense("b", 1.0), _dense("c", 0.6)]
    fused = fuse(dense, [], alpha=1.0, top_k=2)
    assert [chunk.chunk_id for chunk in fused] == ["b", "c"]


def test_fuse_lexical_only_chunk_metadata_preserved():
    lexical = [
        SourceChunk(chunk_id="x", score=1.0, bm25_score_norm=1.0, title="Paper X", text="body")
    ]
    fused = fuse([], lexical, alpha=0.6, top_k=5)
    assert fused[0].title == "Paper X"
    assert abs(fused[0].score - 0.4) < 1e-9  # (1-alpha) * 1.0
