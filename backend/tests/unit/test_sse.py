import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app import sse


async def _collect(agen: AsyncIterator[dict[str, str]]) -> list[dict[str, str]]:
    return [item async for item in agen]


async def _from_list(items: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for item in items:
        yield item


async def _boom(items: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for item in items:
        yield item
    raise RuntimeError("stream blew up")


def test_sse_message_serializes_data():
    msg = sse.sse_message("stage", {"node": "intake", "status": "start"})
    assert msg["event"] == "stage"
    assert json.loads(msg["data"]) == {"node": "intake", "status": "start"}


async def test_to_sse_prepends_accepted_then_events():
    chunks = [
        {"event": "stage", "data": {"node": "intake"}},
        {"event": "token", "data": {"text": "hi"}},
    ]
    out = await _collect(sse.to_sse({"thread_id": "t1"}, _from_list(chunks)))
    assert [m["event"] for m in out] == ["accepted", "stage", "token"]
    assert json.loads(out[0]["data"]) == {"thread_id": "t1"}
    assert json.loads(out[2]["data"]) == {"text": "hi"}


async def test_to_sse_skips_chunks_without_event():
    chunks = [{"data": {"x": 1}}, {"event": "token", "data": {"text": "ok"}}]
    out = await _collect(sse.to_sse({}, _from_list(chunks)))
    assert [m["event"] for m in out] == ["accepted", "token"]


async def test_to_sse_emits_terminal_error_on_exception():
    out = await _collect(sse.to_sse({}, _boom([{"event": "token", "data": {"text": "x"}}])))
    assert out[-1]["event"] == "error"
    assert json.loads(out[-1]["data"])["code"] == "internal"


def test_error_message_coerces_unknown_code():
    msg = sse.error_message("not-a-code", "boom")
    assert json.loads(msg["data"])["code"] == "internal"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
