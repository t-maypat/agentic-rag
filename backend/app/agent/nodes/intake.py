"""Intake: classify + coreference-resolve, and reset per-request state.

Runs first on every turn. Only ``history`` survives across turns; intake resets
every other per-request field (REVAMP_PLAN §3.1 multi-turn semantics).
"""

import time
from typing import Any, Literal

from langgraph.types import Command

from app.agent import budget, events
from app.agent.deps import NodeConfig, get_deps
from app.agent.schemas import IntakeResult
from app.agent.state import ResearchState
from app.prompts import registry


def _format_history(state: ResearchState) -> str:
    turns = state.get("history", [])[-2:]
    if not turns:
        return "(none)"
    lines: list[str] = []
    for turn in turns:
        answer = (turn.answer_md or "").strip().replace("\n", " ")
        if len(answer) > 300:
            answer = answer[:300] + "…"
        lines.append(f"Q: {turn.question}\nA: {answer or '(refused)'}")
    return "\n".join(lines)


def intake(
    state: ResearchState, config: NodeConfig
) -> Command[Literal["plan", "retrieve", "finalize"]]:
    started = time.monotonic()
    events.stage_start("intake")
    deps = get_deps(config)

    ledger = budget.new_ledger()
    prompt = registry.get("intake")
    result = deps.llm.generate_json(
        prompt.render(question=state["question"], history=_format_history(state)),
        IntakeResult,
        ledger=ledger,
        role=prompt.model_role,
        temperature=prompt.temperature,
        prompt_id=prompt.tag,
    )

    # Reset all per-request fields; keep history.
    update: dict[str, Any] = {
        "standalone_question": result.standalone_question or state["question"],
        "route": result.route,
        "redirect_message": result.redirect_message,
        "sub_questions": [],
        "evidence": {},
        "grades": {},
        "rewrite_count": 0,
        "draft_answer": None,
        "sources": [],
        "claims": [],
        "ledger": ledger,
        "outcome": None,
    }

    elapsed = int((time.monotonic() - started) * 1000)
    if result.route == "redirect":
        events.stage_end("intake", "off-topic → redirect", elapsed)
        return Command(goto="finalize", update=update)

    goto = "plan" if state["mode"] == "deep" else "retrieve"
    events.stage_end("intake", f"research → {goto}", elapsed)
    return Command(goto=goto, update=update)
