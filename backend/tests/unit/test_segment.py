"""Claim-segmentation tests: prose, markdown lists, code blocks (§3.4)."""

from app.agent.segment import cited_source_ids, segment_claims


def test_prose_splits_on_sentence_boundaries():
    draft = (
        "SPLADE is a learned sparse retriever that expands query terms effectively [S1]. "
        "It consistently outperforms classic BM25 baselines on passage recall [S2]."
    )
    claims = segment_claims(draft)
    assert claims == [
        "SPLADE is a learned sparse retriever that expands query terms effectively [S1].",
        "It consistently outperforms classic BM25 baselines on passage recall [S2].",
    ]


def test_short_fragment_merges_into_preceding_claim():
    draft = "Retrieval augmented generation improves factual accuracy on open questions. It helps."
    claims = segment_claims(draft)
    assert len(claims) == 1
    assert claims[0].endswith("It helps.")


def test_list_items_are_separate_atomic_claims():
    draft = (
        "The evidence highlights two contributions worth calling out here.\n"
        "- Dense retrieval captures semantic similarity.\n"
        "- BM25 captures exact lexical overlap.\n"
    )
    claims = segment_claims(draft)
    assert "Dense retrieval captures semantic similarity." in claims
    assert "BM25 captures exact lexical overlap." in claims


def test_code_blocks_are_never_audited():
    draft = (
        "Here is how you call the retriever in practice today.\n"
        "```python\n"
        "print('ignore me')\n"
        "```\n"
        "That is the whole interface you need."
    )
    claims = segment_claims(draft)
    assert not any("ignore me" in claim for claim in claims)
    assert any("retriever" in claim for claim in claims)


def test_headings_are_dropped():
    draft = "## Summary\nThe method reduces hallucination on cited answers substantially [S1]."
    claims = segment_claims(draft)
    assert claims == ["The method reduces hallucination on cited answers substantially [S1]."]


def test_cited_source_ids_are_distinct_and_ordered():
    assert cited_source_ids("Backed by [S2] and [S1] and again [S2].") == ["S2", "S1"]
    assert cited_source_ids("No markers here.") == []
