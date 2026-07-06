"""Graph state schema for the Loupe research agent (see REVAMP_PLAN §3.1).

The ``ResearchState`` TypedDict is the single mutable object threaded through the
LangGraph nodes. Per-request fields are reset by the intake node on every turn;
only ``history`` survives across turns via the checkpointer.
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class EvidenceChunk(BaseModel):
    id: str  # stable chunk id (existing scheme)
    source_id: str = ""  # "S1"… assigned at synthesis time
    doc_title: str
    section: str | None = None
    url: str | None = None
    text: str
    origin: Literal["corpus", "web"] = "corpus"
    scores: dict = Field(default_factory=dict)  # {"dense", "bm25", "fused"}
    trust: Literal["normal", "low"] = "normal"


class SubQuestion(BaseModel):
    id: str  # "sq1", "sq2", …
    text: str
    status: Literal["pending", "sufficient", "insufficient", "abandoned"] = "pending"


class EvidenceGrade(BaseModel):
    sub_question_id: str
    score: float  # 0.0–1.0
    sufficient: bool  # score >= 0.6
    missing: str = ""  # uncovered aspect ("" if none)


class ClaimAudit(BaseModel):
    id: str  # "c1", …
    text: str
    verdict: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED"]
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""


class BudgetLedger(BaseModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    web_fetches: int = 0
    started_at: float = 0.0  # time.monotonic()


class QATurn(BaseModel):
    question: str
    answer_md: str | None = None
    outcome: str = ""


class ResearchState(TypedDict):
    question: str  # raw user input for THIS turn
    standalone_question: str  # coreference-resolved by intake
    history: list[QATurn]  # persisted across turns via checkpointer
    mode: Literal["quick", "deep"]
    route: Literal["research", "redirect"] | None
    redirect_message: str | None
    sub_questions: list[SubQuestion]
    evidence: dict[str, list[EvidenceChunk]]  # keyed by sub_question id
    grades: dict[str, EvidenceGrade]
    rewrite_count: int
    draft_answer: str | None
    sources: list[EvidenceChunk]  # S1..Sn selected for synthesis
    claims: list[ClaimAudit]
    ledger: BudgetLedger
    outcome: Literal["answered", "refused", "redirected", "budget_exceeded"] | None
