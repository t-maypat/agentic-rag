import json

from app.retrieval.bm25 import Bm25Index, LexicalChunk, load_chunks, tokenize


def test_tokenize_lowercases_and_splits():
    assert tokenize("Hybrid RAG  Systems!") == ["hybrid", "rag", "systems!"]


def _chunk(chunk_id: str, text: str) -> LexicalChunk:
    return LexicalChunk(
        chunk_id=chunk_id,
        doc_id=chunk_id.split(":")[0],
        title=None,
        section=None,
        source=None,
        authors=None,
        year=None,
        source_type=None,
        url=None,
        text=text,
    )


def test_search_ranks_relevant_chunk_first():
    index = Bm25Index(
        [
            _chunk("a:0", "dense retrieval uses embeddings for semantic search"),
            _chunk("b:0", "bm25 is a lexical ranking function based on term frequency"),
            _chunk("c:0", "transformers rely on attention mechanisms"),
        ]
    )
    results = index.search("what is bm25 lexical ranking", top_k=3)
    assert results[0].chunk_id == "b:0"
    # Top score is normalized to 1.0.
    assert abs(results[0].bm25_score_norm - 1.0) < 1e-9
    assert all(0.0 <= r.bm25_score_norm <= 1.0 for r in results)


def test_search_empty_index_returns_empty():
    assert Bm25Index([]).search("anything", top_k=5) == []
    assert len(Bm25Index([])) == 0


def test_load_chunks_roundtrip(tmp_path):
    path = tmp_path / "chunks.jsonl"
    records = [
        {"chunk_id": "a:0", "doc_id": "a", "title": "A", "text": "alpha beta"},
        {"chunk_id": "a:1", "doc_id": "a", "title": "A", "text": "gamma delta"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    chunks = load_chunks(path)
    assert [c.chunk_id for c in chunks] == ["a:0", "a:1"]
    assert chunks[0].title == "A"


def test_load_chunks_missing_file(tmp_path):
    assert load_chunks(tmp_path / "nope.jsonl") == []
