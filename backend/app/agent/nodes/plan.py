"""Plan (deep mode): decompose into ≤ 3 sub-questions."""

import time
from typing import Any

from app.agent import events
from app.agent.deps import NodeConfig, get_deps
from app.agent.schemas import PlanResult
from app.agent.state import ResearchState, SubQuestion
from app.prompts import registry


def plan(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    started = time.monotonic()
    events.stage_start("plan")
    deps = get_deps(config)

    prompt = registry.get("plan")
    result = deps.llm.generate_json(
        prompt.render(question=state["standalone_question"]),
        PlanResult,
        ledger=state["ledger"],
        role=prompt.model_role,
        temperature=prompt.temperature,
        prompt_id=prompt.tag,
    )

    texts = [text.strip() for text in result.sub_questions if text.strip()][:3]
    if not texts:
        texts = [state["standalone_question"]]
    sub_questions = [SubQuestion(id=f"sq{i}", text=text) for i, text in enumerate(texts, 1)]

    events.emit(events.PLAN, sub_questions=[{"id": sq.id, "text": sq.text} for sq in sub_questions])
    events.stage_end(
        "plan", f"{len(sub_questions)} sub-questions", int((time.monotonic() - started) * 1000)
    )
    return {"sub_questions": sub_questions}
