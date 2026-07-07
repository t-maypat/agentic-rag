"""POST /api/research → text/event-stream (REVAMP_PLAN §6).

Streams the quick/deep corpus+web flow. In Deep mode with ``REQUIRE_DEEP_APPROVAL``
the graph pauses at the approve node (HITL); the stream ends with an ``interrupt``
event and the client resumes via ``POST /api/research/{thread_id}/approve``.
The graph emits SSE-shaped custom events; :func:`app.sse.to_sse` serializes them.
"""

import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from app.agent.runtime import get_deps, get_graph
from app.cache import CachedResponse, make_key, response_cache
from app.models import ResearchRequest
from app.retrieval.index import corpus_version
from app.security.access import public_access
from app.sse import to_sse

router = APIRouter(prefix="/research", tags=["research"])


class ApproveRequest(BaseModel):
    approved: bool


def _pending_interrupt(graph, config: dict[str, Any]) -> dict[str, Any] | None:
    """Return the payload of a pending HITL interrupt for a thread, else None."""
    snapshot = graph.get_state(config)
    if not snapshot:
        return None
    for task in snapshot.tasks:
        for intr in task.interrupts:
            value = intr.value
            if isinstance(value, dict):
                return value
    return None


def _replay(cached: CachedResponse) -> AsyncIterator[Mapping[str, Any]]:
    async def gen() -> AsyncIterator[Mapping[str, Any]]:
        if cached.answer_md:
            yield {"event": "token", "data": {"text": cached.answer_md}}
        yield {"event": "usage", "data": cached.usage}
        yield {
            "event": "done",
            "data": {
                "outcome": cached.outcome,
                "answer_md": cached.answer_md,
                "sources": cached.sources,
                "cached": True,
            },
        }

    return gen()


def _live(
    graph,
    graph_input: Any,
    config: dict[str, Any],
    cache_key: str | None,
) -> AsyncIterator[Mapping[str, Any]]:
    async def gen() -> AsyncIterator[Mapping[str, Any]]:
        usage: dict[str, Any] = {}
        done: dict[str, Any] | None = None
        # The graph is compiled with the sync SqliteSaver (its async methods raise),
        # so drive the sync stream and bridge each chunk to async via the threadpool
        # rather than using astream, which would require an async checkpointer.
        sync_stream = graph.stream(graph_input, config, stream_mode="custom")
        async for chunk in iterate_in_threadpool(sync_stream):
            event = chunk.get("event")
            if event == "usage":
                usage = dict(chunk.get("data", {}))
            elif event == "done":
                done = dict(chunk.get("data", {}))
            yield chunk
        if done is None:
            # No terminal event → the run paused at the HITL approval interrupt.
            payload = _pending_interrupt(graph, config)
            if payload is not None:
                yield {"event": "interrupt", "data": payload}
        elif cache_key is not None:
            response_cache.set(
                cache_key,
                CachedResponse(
                    answer_md=done.get("answer_md"),
                    outcome=done.get("outcome", "answered"),
                    sources=done.get("sources", []),
                    usage=usage,
                ),
            )

    return gen()


@router.post("")
async def research(payload: ResearchRequest, request: Request) -> EventSourceResponse:
    await public_access.enforce_research_access(
        request=request, question=payload.question, captcha_token=payload.captcha_token
    )

    version = corpus_version()
    thread_id = payload.thread_id or uuid.uuid4().hex
    accepted = {"thread_id": thread_id, "mode": payload.mode, "corpus_version": version}

    # Exact-match cache only for fresh threads (follow-ups depend on thread state).
    cache_key = make_key(payload.question, payload.mode, version)
    if payload.thread_id is None:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return EventSourceResponse(
                to_sse(accepted, _replay(cached)), ping=10, headers=_SSE_HEADERS
            )

    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id, "deps": get_deps()}}
    state = {"question": payload.question, "mode": payload.mode}
    # Fresh threads may cache; follow-ups (thread_id supplied) depend on state.
    key = cache_key if payload.thread_id is None else None
    chunks = _live(graph, state, config, key)
    return EventSourceResponse(to_sse(accepted, chunks), ping=10, headers=_SSE_HEADERS)


@router.post("/{thread_id}/approve")
async def approve_research(
    thread_id: str, payload: ApproveRequest, request: Request
) -> EventSourceResponse:
    """Resume a Deep-mode run paused at the HITL approval interrupt (§6).

    Rate-limited (not captcha'd, per §10.1) because resuming triggers the
    expensive tail of the graph — retrieve/web/synthesize/verify LLM calls.
    """
    public_access.check_rate_limit(request)
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id, "deps": get_deps()}}

    if _pending_interrupt(graph, config) is None:
        raise HTTPException(status_code=404, detail="No pending approval for this thread.")

    snapshot = graph.get_state(config)
    mode = snapshot.values.get("mode", "deep")
    accepted = {"thread_id": thread_id, "mode": mode, "corpus_version": corpus_version()}

    resume = Command(resume={"approved": payload.approved})
    chunks = _live(graph, resume, config, None)
    return EventSourceResponse(to_sse(accepted, chunks), ping=10, headers=_SSE_HEADERS)


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
