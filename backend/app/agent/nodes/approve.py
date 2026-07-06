"""Approve (deep mode HITL gate, REVAMP_PLAN §1.1 / §3).

Sits between plan and retrieve. When ``REQUIRE_DEEP_APPROVAL`` is set, the node
calls LangGraph's :func:`interrupt`, pausing the run: the stream ends and the
client must confirm via ``POST /api/research/{thread_id}/approve``. The route
resumes with ``Command(resume={"approved": bool})``, whose value is returned here.

When approval is disabled (dev default) the node is a pass-through, so it needs no
checkpointer and unit tests exercising the deep path stay simple.
"""

from typing import Any, Literal

from langgraph.types import Command, interrupt

from app.agent.deps import NodeConfig
from app.agent.state import ResearchState
from app.core.config import settings

APPROVE_REASON = "approve_web_research"
APPROVE_MESSAGE = "This will search the live web and use more budget — proceed?"
DECLINE_MESSAGE = "Web research was declined, so I did not search the live web."


def _approved(decision: Any) -> bool:
    if isinstance(decision, dict):
        return bool(decision.get("approved"))
    return bool(decision)


def approve(state: ResearchState, config: NodeConfig) -> Command[Literal["retrieve", "finalize"]]:
    if not settings.require_deep_approval:
        return Command(goto="retrieve")

    decision = interrupt({"reason": APPROVE_REASON, "message": APPROVE_MESSAGE})
    if _approved(decision):
        return Command(goto="retrieve")
    # User declined live web research → graceful refusal carrying an explanation
    # (finalize surfaces ``redirect_message`` for a preset refusal, §6).
    update: dict[str, Any] = {"outcome": "refused", "redirect_message": DECLINE_MESSAGE}
    return Command(goto="finalize", update=update)
