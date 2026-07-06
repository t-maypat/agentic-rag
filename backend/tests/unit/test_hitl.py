"""Deep-mode HITL approval interrupt/resume (REVAMP_PLAN §1.1, §3, §6)."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agent.graph import compile_graph
from app.agent.nodes.approve import APPROVE_REASON, DECLINE_MESSAGE
from app.core.config import settings
from tests.unit.conftest import FakeLLM, FakeWebSearch


def _graph():
    return compile_graph(checkpointer=MemorySaver())


def _config(make_deps, fake_corpus, web, thread_id):
    deps = make_deps(FakeLLM(grade_scores=[1.0]), fake_corpus, web)
    return {"configurable": {"thread_id": thread_id, "deps": deps}}


def _pending(graph, config):
    snap = graph.get_state(config)
    return [intr for task in snap.tasks for intr in task.interrupts]


def test_deep_mode_interrupts_before_retrieval(monkeypatch, make_deps, fake_corpus):
    monkeypatch.setattr(settings, "require_deep_approval", True)
    graph = _graph()
    web = FakeWebSearch()
    config = _config(make_deps, fake_corpus, web, "t-interrupt")
    graph.invoke({"question": "what is RAG", "mode": "deep"}, config)

    interrupts = _pending(graph, config)
    assert interrupts
    assert interrupts[0].value["reason"] == APPROVE_REASON
    # Paused at the gate: retrieval (and its web fetch) has not run yet.
    assert web.calls == []
    assert graph.get_state(config).values.get("outcome") is None


def test_approval_resumes_and_runs_web_research(monkeypatch, make_deps, fake_corpus):
    monkeypatch.setattr(settings, "require_deep_approval", True)
    graph = _graph()
    web = FakeWebSearch()
    config = _config(make_deps, fake_corpus, web, "t-approve")
    graph.invoke({"question": "what is RAG", "mode": "deep"}, config)

    final = graph.invoke(Command(resume={"approved": True}), config)
    assert final["outcome"] == "answered"
    assert web.calls  # web research actually ran after approval
    assert not _pending(graph, config)


def test_decline_refuses_gracefully_without_web(monkeypatch, make_deps, fake_corpus):
    monkeypatch.setattr(settings, "require_deep_approval", True)
    graph = _graph()
    web = FakeWebSearch()
    config = _config(make_deps, fake_corpus, web, "t-decline")
    graph.invoke({"question": "what is RAG", "mode": "deep"}, config)

    final = graph.invoke(Command(resume={"approved": False}), config)
    assert final["outcome"] == "refused"
    assert web.calls == []  # declined → no live web fetch
    assert final["draft_answer"] == DECLINE_MESSAGE  # decline carries its message


def test_no_interrupt_when_approval_disabled(monkeypatch, make_deps, fake_corpus):
    monkeypatch.setattr(settings, "require_deep_approval", False)
    graph = _graph()
    web = FakeWebSearch()
    config = _config(make_deps, fake_corpus, web, "t-noapprove")
    final = graph.invoke({"question": "what is RAG", "mode": "deep"}, config)
    assert final["outcome"] == "answered"
    assert not _pending(graph, config)
    assert web.calls  # deep mode still runs web research, just without the gate
