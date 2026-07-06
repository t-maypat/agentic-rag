"""Rewrite: refine retrieval queries for insufficient sub-questions."""

import time
from typing import Any

from app.agent import events
from app.agent.deps import NodeConfig, get_deps
from app.agent.schemas import RewriteResult
from app.agent.state import ResearchState
from app.prompts import registry


def _render_blocks(state: ResearchState) -> str:
    lines: list[str] = []
    for sq in state["sub_questions"]:
        if sq.status != "insufficient":
            continue
        missing = state["grades"].get(sq.id)
        gap = missing.missing if missing else ""
        lines.append(f"[{sq.id}] {sq.text} | missing: {gap or 'more relevant evidence'}")
    return "\n".join(lines)


def rewrite(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    started = time.monotonic()
    events.stage_start("rewrite", iteration=state["rewrite_count"])
    deps = get_deps(config)

    prompt = registry.get("rewrite")
    result = deps.llm.generate_json(
        prompt.render(blocks=_render_blocks(state)),
        RewriteResult,
        ledger=state["ledger"],
        role=prompt.model_role,
        temperature=prompt.temperature,
        prompt_id=prompt.tag,
    )

    new_queries = {item.sub_question_id: item.query.strip() for item in result.queries}
    sub_questions = list(state["sub_questions"])
    changed = 0
    for sq in sub_questions:
        if sq.status == "insufficient" and new_queries.get(sq.id):
            sq.text = new_queries[sq.id]
            changed += 1

    events.stage_end(
        "rewrite",
        f"{changed} query(ies) refined",
        int((time.monotonic() - started) * 1000),
        iteration=state["rewrite_count"],
    )
    return {"sub_questions": sub_questions, "rewrite_count": state["rewrite_count"] + 1}
