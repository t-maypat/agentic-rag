"""Verify-node tests with a stubbed judge — no network, no real LLM."""

from app.agent import budget
from app.agent.deps import AgentDeps
from app.agent.nodes.verify import verify
from app.agent.schemas import ClaimVerdict, VerifyResult
from app.agent.state import EvidenceChunk
from tests.unit.conftest import FakeLLM


def _sources() -> list[EvidenceChunk]:
    return [
        EvidenceChunk(
            id="c1",
            source_id="S1",
            doc_title="RAG Survey",
            text="RAG combines retrieval and generation.",
        ),
        EvidenceChunk(
            id="c2", source_id="S2", doc_title="SPLADE", text="SPLADE is a sparse retriever."
        ),
    ]


def _state(draft: str) -> dict:
    return {"draft_answer": draft, "sources": _sources(), "ledger": budget.new_ledger()}


def _run(llm: FakeLLM, draft: str):
    deps = AgentDeps(llm=llm, search_corpus=lambda q, k=8: [])
    return verify(_state(draft), {"configurable": {"deps": deps}})


def test_uncited_fabricated_sentence_is_unsupported():
    # Uncited factual sentence; strict stub judge marks it UNSUPPORTED.
    draft = "The corpus proves that sparse retrieval was invented in the year 3000."
    result = _run(FakeLLM(), draft)
    assert len(result["claims"]) == 1
    assert result["claims"][0].verdict == "UNSUPPORTED"
    assert result["claims"][0].evidence_ids == ["S1", "S2"]  # judged against all sources


def test_uncited_claim_is_capped_at_partial():
    # Even if the judge says SUPPORTED, an uncited claim can be at best PARTIAL.
    draft = "Sparse retrievers generally outperform dense retrievers on lexical overlap tasks."
    result = _run(FakeLLM(verify_verdict=lambda line: "SUPPORTED"), draft)
    assert result["claims"][0].verdict == "PARTIAL"


def test_cited_claim_is_supported_against_its_sources():
    draft = "RAG combines retrieval and generation [S1]."
    result = _run(FakeLLM(), draft)
    claim = result["claims"][0]
    assert claim.verdict == "SUPPORTED"
    assert claim.evidence_ids == ["S1"]


def test_no_draft_returns_no_claims():
    deps = AgentDeps(llm=FakeLLM(), search_corpus=lambda q, k=8: [])
    result = verify(
        {"draft_answer": None, "sources": _sources(), "ledger": budget.new_ledger()},
        {"configurable": {"deps": deps}},
    )
    assert result == {"claims": []}


class _MismatchLLM(FakeLLM):
    def generate_json(self, prompt, schema, *, ledger, **kw):
        if schema is VerifyResult:
            budget.record_llm(ledger, 10, 5)
            # Return the wrong number of verdicts → ids won't match the claims.
            return VerifyResult(claims=[ClaimVerdict(id="cX", verdict="SUPPORTED")])
        return super().generate_json(prompt, schema, ledger=ledger, **kw)


def test_id_mismatch_refuses_instead_of_guessing():
    draft = "RAG combines retrieval and generation [S1]. It reduces hallucination [S2]."
    result = _run(_MismatchLLM(), draft)
    assert result == {"claims": [], "outcome": "refused"}
