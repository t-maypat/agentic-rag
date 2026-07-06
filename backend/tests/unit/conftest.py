"""Shared fakes for agent unit tests — zero network, zero real LLM/Pinecone."""

from collections.abc import Iterator

import pytest

from app.agent import budget
from app.agent.deps import AgentDeps
from app.agent.schemas import (
    GradeItem,
    GradeResult,
    IntakeResult,
    PlanResult,
    RewriteItem,
    RewriteResult,
)
from app.agent.state import BudgetLedger, EvidenceChunk


class FakeLLM:
    """Deterministic LLMClient stub. Records every call and its schema."""

    def __init__(
        self,
        *,
        intake: IntakeResult | None = None,
        plan: PlanResult | None = None,
        grade_scores: list[float] | None = None,
        synth: str = "The answer is grounded [S1].",
    ) -> None:
        self.intake = intake or IntakeResult(route="research", standalone_question="")
        self.plan = plan
        # One score per grade *call* (to drive the rewrite loop); last value repeats.
        self.grade_scores = grade_scores or [1.0]
        self.synth = synth
        self.calls: list[str] = []
        self._grade_i = 0

    def generate(self, prompt: str, *, ledger: BudgetLedger, **kw: object) -> str:
        budget.record_llm(ledger, 10, 5)
        self.calls.append("generate")
        return "text"

    def generate_stream(self, prompt: str, *, ledger: BudgetLedger, **kw: object) -> Iterator[str]:
        self.calls.append("generate_stream")
        for token in self.synth.split(" "):
            yield token + " "
        budget.record_llm(ledger, 50, 20)

    def generate_json(self, prompt: str, schema, *, ledger: BudgetLedger, **kw: object):
        budget.record_llm(ledger, 10, 5)
        self.calls.append(schema.__name__)
        if schema is IntakeResult:
            result = self.intake
            if not result.standalone_question:
                # Echo the question so downstream nodes have something to retrieve.
                return IntakeResult(
                    route=result.route,
                    standalone_question="what is retrieval augmented generation",
                    redirect_message=result.redirect_message,
                )
            return result
        if schema is PlanResult:
            return self.plan or PlanResult(sub_questions=["sub one", "sub two"])
        if schema is GradeResult:
            score = self.grade_scores[min(self._grade_i, len(self.grade_scores) - 1)]
            self._grade_i += 1
            # Grade every sub-question present in the prompt with the same score.
            ids = [line.split("]")[0][1:] for line in prompt.splitlines() if line.startswith("[sq")]
            if not ids:
                ids = ["sq1"]
            return GradeResult(
                grades=[GradeItem(sub_question_id=i, score=score, missing="gap") for i in ids]
            )
        if schema is RewriteResult:
            ids = [line.split("]")[0][1:] for line in prompt.splitlines() if line.startswith("[sq")]
            return RewriteResult(
                queries=[RewriteItem(sub_question_id=i, query=f"refined {i}") for i in ids]
            )
        raise AssertionError(f"unexpected schema {schema!r}")


class FakeCorpus:
    def __init__(self, chunks: list[EvidenceChunk] | None = None) -> None:
        self.chunks = chunks
        self.calls: list[str] = []

    def __call__(self, query: str, top_k: int = 8) -> list[EvidenceChunk]:
        self.calls.append(query)
        if self.chunks is not None:
            return self.chunks
        return [
            EvidenceChunk(
                id=f"c-{len(self.calls)}",
                doc_title="RAG Survey",
                section="Intro",
                text="Retrieval-augmented generation combines retrieval with generation.",
                origin="corpus",
                scores={"dense": 0.9, "bm25": 0.8, "fused": 0.87},
            )
        ]


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_corpus() -> FakeCorpus:
    return FakeCorpus()


@pytest.fixture
def make_deps():
    def _make(llm: FakeLLM, corpus: FakeCorpus) -> AgentDeps:
        return AgentDeps(llm=llm, search_corpus=corpus)

    return _make
