"""GET /api/threads/{thread_id} — last-state summary for page-refresh recovery (§6)."""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.agent.runtime import get_graph

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("/{thread_id}")
async def thread_summary(thread_id: str) -> dict[str, Any]:
    graph = get_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    values = snapshot.values if snapshot else None
    if not values or not values.get("history"):
        raise HTTPException(status_code=404, detail="Unknown thread.")
    last = values["history"][-1]
    sources = values.get("sources") or []
    return {
        "question": last.question,
        "outcome": last.outcome,
        "answer_md": last.answer_md,
        "claims": [claim.model_dump() for claim in values.get("claims", [])],
        "sources": [source.model_dump() for source in sources],
    }
