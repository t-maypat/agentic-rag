"""Custom stream-event helpers.

Nodes emit SSE-shaped events (``{"event": name, "data": {...}}``) into LangGraph's
custom stream via ``get_stream_writer``. Outside a graph run (direct-call unit
tests) the writer is unavailable, so emission is a safe no-op. The SSE route reads
these back with ``graph.astream(..., stream_mode="custom")`` and serializes them.
"""

from typing import Any

from langgraph.config import get_stream_writer

from app import observability

# Event names (kept in sync with the SSE contract, REVAMP_PLAN §6).
STAGE = "stage"
PLAN = "plan"
EVIDENCE = "evidence"
INTERRUPT = "interrupt"
TOKEN = "token"
CLAIMS = "claims"
USAGE = "usage"
DONE = "done"


def emit(event: str, **data: Any) -> None:
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return  # not inside a graph run (e.g. direct unit test) -> no-op
    writer({"event": event, "data": data})


def stage_start(node: str, iteration: int = 0) -> None:
    # Each node calls this exactly once (start) and stage_end once (any return
    # path), synchronously within one node execution — so the span opened here is
    # closed in the same thread/context, and LLM generations in between attach to it.
    observability.node_start(node, iteration)
    emit(STAGE, node=node, status="start", summary="", elapsed_ms=0, iteration=iteration)


def stage_end(node: str, summary: str, elapsed_ms: int, iteration: int = 0) -> None:
    observability.node_end(node, summary, elapsed_ms)
    emit(
        STAGE, node=node, status="end", summary=summary, elapsed_ms=elapsed_ms, iteration=iteration
    )
