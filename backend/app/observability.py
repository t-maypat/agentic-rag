"""Langfuse tracing — env-gated, no-op fallback (REVAMP_PLAN §9).

One **trace** per request, a **span** per graph node, and a **generation** per
LLM call (tagged with model, tokens, latency, and ``prompt_id@version``). When the
Langfuse keys are absent — every local run and every unit test — all functions are
cheap no-ops: the SDK is never imported and no socket is opened, so "no network in
unit tests" (§2.3) holds without special-casing tests.

The seam is deliberately object-free at the call sites: nodes and the LLM adapter
call plain module functions, and the current trace/span are carried in
``contextvars`` so nothing has to be threaded through the graph state or the
``LLMClient`` protocol. The contextvars propagate into LangGraph's threadpool
workers because ``iterate_in_threadpool`` copies the calling context per step.
"""

import contextvars
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("loupe.observability")

# Lazily-created Langfuse client (or None when disabled/unavailable).
_client: Any = None
_initialized = False

# The active request trace and the currently-open node span. Read by
# record_generation() to parent generations under the right node.
_active_trace: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "loupe_active_trace", default=None
)
_active_span: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "loupe_active_span", default=None
)


def _get_client() -> Any:
    """Return the Langfuse client, constructing it once. None when disabled."""
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
        )
        logger.info("Langfuse tracing enabled (host=%s)", settings.langfuse_host or "default")
    except Exception:  # noqa: BLE001 — tracing must never break the request path
        logger.warning("Langfuse init failed; tracing disabled", exc_info=True)
        _client = None
    return _client


def is_enabled() -> bool:
    return _get_client() is not None


def start_trace(*, name: str, thread_id: str, question: str, mode: str) -> Any:
    """Open a request-level trace and mark it active. Returns None when disabled.

    Sets the ``_active_trace`` contextvar in the *current* async context so that
    node spans created later in LangGraph's worker threads attach to it.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        trace = client.trace(
            name=name,
            session_id=thread_id,
            input={"question": question, "mode": mode},
            metadata={"mode": mode},
            tags=[mode],
        )
    except Exception:  # noqa: BLE001
        logger.debug("start_trace failed", exc_info=True)
        return None
    _active_trace.set(trace)
    return trace


def end_trace(trace: Any, *, outcome: str | None = None, usage: dict | None = None) -> None:
    if trace is None:
        return
    try:
        metadata = {"usage": usage} if usage else None
        trace.update(output={"outcome": outcome}, metadata=metadata)
    except Exception:  # noqa: BLE001
        logger.debug("end_trace failed", exc_info=True)


def node_start(node: str, iteration: int = 0) -> None:
    """Open a span for a graph node under the active trace (no-op when disabled)."""
    trace = _active_trace.get()
    if trace is None:
        _active_span.set(None)
        return
    try:
        span = trace.span(name=node, metadata={"iteration": iteration})
    except Exception:  # noqa: BLE001
        logger.debug("node_start failed", exc_info=True)
        span = None
    _active_span.set(span)


def node_end(node: str, summary: str, elapsed_ms: int = 0) -> None:
    span = _active_span.get()
    _active_span.set(None)
    if span is None:
        return
    try:
        span.end(output=summary, metadata={"elapsed_ms": elapsed_ms})
    except Exception:  # noqa: BLE001
        logger.debug("node_end failed", exc_info=True)


def record_generation(
    *,
    model: str,
    prompt_id: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    temperature: float | None = None,
) -> None:
    """Log one LLM generation under the current node span (or trace)."""
    parent = _active_span.get() or _active_trace.get()
    if parent is None:
        return
    try:
        gen = parent.generation(
            name=prompt_id or "llm",
            model=model,
            model_parameters=({"temperature": temperature} if temperature is not None else None),
            usage={
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
                "unit": "TOKENS",
            },
            metadata={"prompt_id": prompt_id, "latency_ms": latency_ms},
        )
        gen.end()
    except Exception:  # noqa: BLE001
        logger.debug("record_generation failed", exc_info=True)


def flush() -> None:
    """Flush buffered events to Langfuse. Safe to call when disabled."""
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:  # noqa: BLE001
        logger.debug("flush failed", exc_info=True)
