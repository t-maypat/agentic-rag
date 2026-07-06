"""Finalize: decide the outcome, emit usage + done, and record the turn.

Handles every terminal path — answered, refused, redirected, budget_exceeded —
and appends the turn to ``history`` (the only field that survives across turns).
"""

from typing import Any

from app.agent import budget, events
from app.agent.deps import NodeConfig
from app.agent.state import EvidenceChunk, QATurn, ResearchState
from app.core.config import settings

_SOURCE_TEXT_LIMIT = 400


def _source_lite(chunk: EvidenceChunk) -> dict[str, Any]:
    text = chunk.text
    if len(text) > _SOURCE_TEXT_LIMIT:
        text = text[:_SOURCE_TEXT_LIMIT].rstrip() + "…"
    return {
        "id": chunk.id,
        "source_id": chunk.source_id,
        "doc_title": chunk.doc_title,
        "section": chunk.section,
        "url": chunk.url,
        "origin": chunk.origin,
        "scores": chunk.scores,
        "trust": chunk.trust,
        "text": text,
    }


def _decide(state: ResearchState) -> tuple[str, str | None]:
    if state.get("route") == "redirect":
        return "redirected", state.get("redirect_message")
    if state.get("outcome") == "budget_exceeded":
        # Budget hit before a draft existed → graceful refusal (draft is None).
        return "budget_exceeded", state.get("draft_answer")
    draft = state.get("draft_answer")
    if draft:
        return "answered", draft
    return "refused", None


def finalize(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    outcome, answer_md = _decide(state)
    ledger = state["ledger"]
    sources = state.get("sources") or []

    events.emit(
        events.USAGE,
        llm_calls=ledger.llm_calls,
        input_tokens=ledger.input_tokens,
        output_tokens=ledger.output_tokens,
        web_fetches=ledger.web_fetches,
        est_cost_usd=budget.est_cost_usd(ledger, settings.model_synth, settings.model_control),
        wall_ms=budget.wall_ms(ledger),
    )
    events.emit(
        events.DONE,
        outcome=outcome,
        answer_md=answer_md,
        sources=[_source_lite(chunk) for chunk in sources],
        cached=False,
    )

    turn = QATurn(question=state["question"], answer_md=answer_md, outcome=outcome)
    history = list(state.get("history", [])) + [turn]
    return {"outcome": outcome, "draft_answer": answer_md, "history": history}
