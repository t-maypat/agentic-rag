"""Grade: judge evidence sufficiency per sub-question, then route.

This node is the gate of the retrieve → rewrite loop and therefore the natural
place the budget governor is consulted: a hard :class:`BudgetExceeded` here routes
straight to finalize with ``outcome="budget_exceeded"``.
"""

import time
from typing import Any, Literal

from langgraph.types import Command

from app.agent import budget, events
from app.agent.deps import NodeConfig, get_deps
from app.agent.errors import BudgetExceeded
from app.agent.schemas import GradeResult
from app.agent.state import EvidenceGrade, ResearchState
from app.prompts import registry

_SUFFICIENT = 0.6
_GRADE_TEXT_LIMIT = 500


def _render_blocks(state: ResearchState) -> str:
    blocks: list[str] = []
    for sq in state["sub_questions"]:
        blocks.append(f"[{sq.id}] {sq.text}")
        chunks = state["evidence"].get(sq.id, [])
        if not chunks:
            blocks.append("  (no evidence retrieved)")
        for chunk in chunks:
            text = chunk.text[:_GRADE_TEXT_LIMIT].replace("\n", " ")
            blocks.append(f"  - {chunk.doc_title}: {text}")
        blocks.append("")
    return "\n".join(blocks)


def grade(
    state: ResearchState, config: NodeConfig
) -> Command[Literal["rewrite", "synthesize", "finalize"]]:
    started = time.monotonic()
    events.stage_start("grade", iteration=state["rewrite_count"])
    deps = get_deps(config)

    prompt = registry.get("grade")
    result = deps.llm.generate_json(
        prompt.render(blocks=_render_blocks(state)),
        GradeResult,
        ledger=state["ledger"],
        role=prompt.model_role,
        temperature=prompt.temperature,
        prompt_id=prompt.tag,
    )

    by_id = {item.sub_question_id: item for item in result.grades}
    grades: dict[str, EvidenceGrade] = {}
    sub_questions = list(state["sub_questions"])
    for sq in sub_questions:
        item = by_id.get(sq.id)
        score = max(0.0, min(1.0, float(item.score))) if item else 0.0
        sufficient = score >= _SUFFICIENT
        grades[sq.id] = EvidenceGrade(
            sub_question_id=sq.id,
            score=score,
            sufficient=sufficient,
            missing=(item.missing if item else "no evidence"),
        )
        sq.status = "sufficient" if sufficient else "insufficient"

    update: dict[str, Any] = {"grades": grades, "sub_questions": sub_questions}
    elapsed = int((time.monotonic() - started) * 1000)

    try:
        budget.check(state["ledger"], state["mode"])
    except BudgetExceeded:
        update["outcome"] = "budget_exceeded"
        events.stage_end(
            "grade", "budget exceeded → finalize", elapsed, iteration=state["rewrite_count"]
        )
        return Command(goto="finalize", update=update)

    all_sufficient = all(grade_row.sufficient for grade_row in grades.values())
    if all_sufficient:
        events.stage_end(
            "grade", "sufficient → synthesize", elapsed, iteration=state["rewrite_count"]
        )
        return Command(goto="synthesize", update=update)
    if state["rewrite_count"] >= budget.MAX_REWRITES:
        events.stage_end(
            "grade",
            "budget of rewrites spent → synthesize",
            elapsed,
            iteration=state["rewrite_count"],
        )
        return Command(goto="synthesize", update=update)

    events.stage_end("grade", "insufficient → rewrite", elapsed, iteration=state["rewrite_count"])
    return Command(goto="rewrite", update=update)
