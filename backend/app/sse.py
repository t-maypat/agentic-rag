"""SSE translation: LangGraph custom-stream events → the wire schema (§6).

Nodes emit ``{"event": name, "data": {...}}`` dicts into the graph's custom
stream. :func:`to_sse` prepends the mandatory ``accepted`` event, serializes each
chunk into an ``EventSourceResponse``-compatible dict, and turns an exception into
a terminal ``error`` event. It is agnostic to where the stream comes from, so it is
unit-tested with a plain fake async iterator (no graph, no network).
"""

import json
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

logger = logging.getLogger("loupe.sse")

# Terminal error codes (§6).
ERROR_CODES = {"rate_limited", "captcha_failed", "budget_exceeded", "internal"}


def sse_message(event: str, data: Mapping[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def error_message(code: str, message: str) -> dict[str, str]:
    if code not in ERROR_CODES:
        code = "internal"
    return sse_message("error", {"code": code, "message": message})


async def to_sse(
    accepted: Mapping[str, Any],
    chunks: AsyncIterator[Mapping[str, Any]],
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE-ready dicts: ``accepted`` first, then each node event, then
    (on failure) a single ``error`` event. Never raises to the caller."""
    yield sse_message("accepted", accepted)
    try:
        async for chunk in chunks:
            event = chunk.get("event")
            data = chunk.get("data", {})
            if not event:
                continue
            yield sse_message(str(event), data)
    except Exception:  # noqa: BLE001 — surfaced as a terminal error event, details logged
        logger.exception("research stream failed")
        yield error_message("internal", "The research run failed unexpectedly.")
