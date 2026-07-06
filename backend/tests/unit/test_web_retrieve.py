"""Deep-mode web research: corpus+web mixing, fetch cap, low-trust exclusion."""

from app.agent import budget
from app.agent.graph import compile_graph
from app.agent.state import EvidenceChunk
from tests.unit.conftest import FakeLLM, FakeWebSearch

GRAPH = compile_graph()


def _run(deps, question="what is RAG", mode="deep"):
    config = {"configurable": {"deps": deps}}
    return GRAPH.invoke({"question": question, "mode": mode}, config)


def _web_chunk(trust="normal", cid="web-x"):
    return EvidenceChunk(
        id=cid,
        doc_title="Blog post",
        url="https://example.com/rag",
        text="Web article on retrieval-augmented generation.",
        origin="web",
        scores={"dense": None, "bm25": None, "fused": 0.5},
        trust=trust,
    )


def test_deep_mode_mixes_corpus_and_web(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    web = FakeWebSearch()
    state = _run(make_deps(llm, fake_corpus, web))
    assert state["outcome"] == "answered"
    # Web tool queried once per sub-question; evidence carries both origins.
    assert web.calls
    origins = {c.origin for chunks in state["evidence"].values() for c in chunks}
    assert origins == {"corpus", "web"}
    # A normal-trust web chunk reaches the synthesis source set with its badge.
    assert any(s.origin == "web" for s in state["sources"])


def test_web_fetches_recorded_and_capped(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    web = FakeWebSearch()
    state = _run(make_deps(llm, fake_corpus, web))
    # 2 planned sub-questions → 2 fetches, within the cap.
    assert state["ledger"].web_fetches == 2
    assert state["ledger"].web_fetches <= budget.MAX_WEB_FETCHES


def test_low_trust_web_chunk_excluded_from_synthesis(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    web = FakeWebSearch(chunks=[_web_chunk(trust="low", cid="web-hostile")])
    state = _run(make_deps(llm, fake_corpus, web))
    # Present as evidence (drawer) but never selected as a synthesis source (§10.2).
    all_evidence_ids = {c.id for chunks in state["evidence"].values() for c in chunks}
    assert "web-hostile" in all_evidence_ids
    assert all(s.id != "web-hostile" for s in state["sources"])


def test_quick_mode_never_calls_web(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    web = FakeWebSearch()
    _run(make_deps(llm, fake_corpus, web), mode="quick")
    assert web.calls == []


def test_web_tool_unavailable_degrades_gracefully(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    web = FakeWebSearch(available=False)
    state = _run(make_deps(llm, fake_corpus, web))
    assert state["outcome"] == "answered"
    assert web.calls == []  # unavailable tool is never queried
    assert state["ledger"].web_fetches == 0
