"""Finalize refusal-contract tests (§1.2.3) — pure decision logic."""

from app.agent.nodes.finalize import _decide
from app.agent.state import ClaimAudit, EvidenceGrade


def _claim(verdict: str) -> ClaimAudit:
    return ClaimAudit(id="c1", text="x", verdict=verdict)


def _sufficient() -> dict[str, EvidenceGrade]:
    return {"sq1": EvidenceGrade(sub_question_id="sq1", score=0.9, sufficient=True)}


def test_answered_when_evidence_sufficient_and_claims_supported():
    state = {
        "draft_answer": "An answer [S1].",
        "grades": _sufficient(),
        "claims": [_claim("SUPPORTED"), _claim("PARTIAL")],
    }
    assert _decide(state) == ("answered", "An answer [S1].")


def test_refused_when_grading_never_sufficient():
    state = {
        "draft_answer": "A shaky answer [S1].",
        "grades": {"sq1": EvidenceGrade(sub_question_id="sq1", score=0.2, sufficient=False)},
        "claims": [_claim("SUPPORTED")],
    }
    assert _decide(state) == ("refused", None)


def test_refused_when_too_many_claims_unsupported():
    state = {
        "draft_answer": "An answer [S1].",
        "grades": _sufficient(),
        "claims": [_claim("UNSUPPORTED"), _claim("UNSUPPORTED"), _claim("SUPPORTED")],
    }
    assert _decide(state) == ("refused", None)


def test_answered_when_unsupported_within_threshold():
    # 1/4 = 25% ≤ 30% → still answered.
    state = {
        "draft_answer": "An answer [S1].",
        "grades": _sufficient(),
        "claims": [_claim("UNSUPPORTED")] + [_claim("SUPPORTED")] * 3,
    }
    assert _decide(state)[0] == "answered"


def test_verify_refused_outcome_is_honored():
    state = {"draft_answer": "x", "outcome": "refused", "grades": _sufficient(), "claims": []}
    assert _decide(state) == ("refused", None)


def test_redirect_takes_priority():
    state = {"route": "redirect", "redirect_message": "I cover AI research."}
    assert _decide(state) == ("redirected", "I cover AI research.")
