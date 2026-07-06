"""Pydantic response schemas for structured-output LLM nodes.

These are the ``response_schema`` shapes passed to Gemini; nodes translate them
into the richer domain types in :mod:`app.agent.state`.
"""

from typing import Literal

from pydantic import BaseModel


class IntakeResult(BaseModel):
    route: Literal["research", "redirect"]
    standalone_question: str
    redirect_message: str | None = None


class PlanResult(BaseModel):
    sub_questions: list[str]


class GradeItem(BaseModel):
    sub_question_id: str
    score: float
    missing: str = ""


class GradeResult(BaseModel):
    grades: list[GradeItem]


class RewriteItem(BaseModel):
    sub_question_id: str
    query: str


class RewriteResult(BaseModel):
    queries: list[RewriteItem]


class ClaimVerdict(BaseModel):
    id: str  # "c1", … — must match the claim ids given in the prompt
    verdict: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED"]
    note: str = ""


class VerifyResult(BaseModel):
    claims: list[ClaimVerdict]
