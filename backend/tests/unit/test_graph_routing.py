"""Graph routing tests with a stubbed LLMClient — no network, no checkpointer."""

from app.agent import budget
from app.agent.graph import compile_graph
from app.agent.schemas import IntakeResult
from tests.unit.conftest import FakeLLM

GRAPH = compile_graph()


def _run(deps, question="what is RAG", mode="quick"):
    config = {"configurable": {"deps": deps}}
    return GRAPH.invoke({"question": question, "mode": mode}, config)


def test_quick_answered(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    state = _run(make_deps(llm, fake_corpus))
    assert state["outcome"] == "answered"
    assert state["draft_answer"]
    assert state["sources"] and state["sources"][0].source_id == "S1"
    # quick mode skips planning.
    assert "PlanResult" not in llm.calls
    assert len(fake_corpus.calls) == 1


def test_deep_mode_plans(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    state = _run(make_deps(llm, fake_corpus), mode="deep")
    assert state["outcome"] == "answered"
    assert "PlanResult" in llm.calls
    assert len(state["sub_questions"]) == 2
    # retrieve ran once per planned sub-question.
    assert len(fake_corpus.calls) == 2


def test_redirect_skips_retrieval(make_deps, fake_corpus):
    llm = FakeLLM(
        intake=IntakeResult(
            route="redirect", standalone_question="hi", redirect_message="I cover AI research."
        )
    )
    state = _run(make_deps(llm, fake_corpus))
    assert state["outcome"] == "redirected"
    assert state["draft_answer"] == "I cover AI research."
    assert fake_corpus.calls == []


def test_rewrite_loop_runs_once(make_deps, fake_corpus):
    # First grade insufficient, second sufficient -> one rewrite, two retrievals.
    llm = FakeLLM(grade_scores=[0.1, 1.0])
    state = _run(make_deps(llm, fake_corpus))
    assert state["outcome"] == "answered"
    assert state["rewrite_count"] == 1
    assert "RewriteResult" in llm.calls
    assert len(fake_corpus.calls) == 2


def test_rewrite_loop_capped(make_deps, fake_corpus):
    # Always insufficient -> capped at MAX_REWRITES, then best-effort synthesize.
    llm = FakeLLM(grade_scores=[0.1])
    state = _run(make_deps(llm, fake_corpus))
    assert state["rewrite_count"] == budget.MAX_REWRITES
    # retrieve runs MAX_REWRITES + 1 times.
    assert len(fake_corpus.calls) == budget.MAX_REWRITES + 1
    assert state["outcome"] == "answered"


def test_budget_exceeded_routes_to_finalize(make_deps, fake_corpus, monkeypatch):
    # After intake(1) + grade(1) json calls, llm_calls == 2 hits the cap.
    monkeypatch.setattr(budget, "MAX_LLM_CALLS", 2)
    llm = FakeLLM(grade_scores=[1.0])
    state = _run(make_deps(llm, fake_corpus))
    assert state["outcome"] == "budget_exceeded"
    assert state["draft_answer"] is None
    # never reached synthesis.
    assert "generate_stream" not in llm.calls


async def test_stream_emits_token_and_done(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    config = {"configurable": {"deps": make_deps(llm, fake_corpus)}}
    events = []
    async for chunk in GRAPH.astream(
        {"question": "what is RAG", "mode": "quick"}, config, stream_mode="custom"
    ):
        events.append(chunk["event"])
    assert "token" in events
    assert "usage" in events
    assert events[-1] == "done"


def test_history_records_turn(make_deps, fake_corpus):
    llm = FakeLLM(grade_scores=[1.0])
    state = _run(make_deps(llm, fake_corpus))
    assert len(state["history"]) == 1
    assert state["history"][0].outcome == "answered"
