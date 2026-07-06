"""POST /api/research → text/event-stream (REVAMP_PLAN §6).

Phase 1 streams the quick/deep corpus flow (no HITL interrupt, no claim audit).
The graph emits SSE-shaped custom events; :func:`app.sse.to_sse` serializes them.
"""

import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.runtime import get_deps, get_graph
from app.cache import CachedResponse, make_key, response_cache
from app.models import ResearchRequest
from app.retrieval.index import corpus_version
from app.security.access import public_access
from app.sse import to_sse

router = APIRouter(prefix="/research", tags=["research"])


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
    graph, state: dict[str, Any], config: dict[str, Any], cache_key: str
) -> AsyncIterator[Mapping[str, Any]]:
    async def gen() -> AsyncIterator[Mapping[str, Any]]:
        usage: dict[str, Any] = {}
        done: dict[str, Any] | None = None
        async for chunk in graph.astream(state, config, stream_mode="custom"):
            event = chunk.get("event")
            if event == "usage":
                usage = dict(chunk.get("data", {}))
            elif event == "done":
                done = dict(chunk.get("data", {}))
            yield chunk
        if done is not None:
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
    chunks = _live(graph, state, config, cache_key)
    return EventSourceResponse(to_sse(accepted, chunks), ping=10, headers=_SSE_HEADERS)


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
