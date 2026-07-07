"""Loupe as an MCP server (FastMCP, stdio) — REVAMP_PLAN §12.

Exposes two tools to any MCP client (e.g. Claude Desktop):

- ``search_corpus(query, top_k=5)`` — hybrid corpus retrieval, returns evidence.
- ``research(question)`` — runs the full agent graph in quick mode (no streaming)
  and returns ``{answer_md, outcome, claims, sources}``.

This reuses the exact same adapters, tools, and graph as the HTTP API — zero
duplicated logic. Run it directly (``uv run python mcp_server.py``); the config
snippet in the README wires it into Claude Desktop.
"""

import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("loupe")


@mcp.tool()
def search_corpus(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search the curated AI/RAG corpus with hybrid (dense + BM25) retrieval.

    Returns the top evidence chunks with their fused/dense/bm25 scores.
    """
    from app.agent.tools import search_corpus as _search_corpus
    from app.retrieval.index import init_retrieval

    init_retrieval()
    return [chunk.model_dump() for chunk in _search_corpus(query, top_k)]


@mcp.tool()
def research(question: str) -> dict[str, Any]:
    """Run the full Loupe research agent (quick mode) over the corpus.

    Returns the cited answer, the per-claim audit, the outcome (``answered`` /
    ``refused`` / ``redirected`` / ``budget_exceeded``), and the sources. Refusals
    are a feature: when the evidence doesn't hold up, ``outcome`` is ``refused``.
    """
    from app.agent.runtime import get_deps, get_graph
    from app.retrieval.index import init_retrieval

    init_retrieval()
    graph = get_graph()
    config = {
        "configurable": {"thread_id": uuid.uuid4().hex, "deps": get_deps()},
    }

    claims: list[dict[str, Any]] = []
    done: dict[str, Any] = {}
    for chunk in graph.stream(
        {"question": question, "mode": "quick"}, config, stream_mode="custom"
    ):
        event = chunk.get("event")
        if event == "claims":
            claims = chunk.get("data", {}).get("claims", [])
        elif event == "done":
            done = dict(chunk.get("data", {}))

    return {
        "answer_md": done.get("answer_md"),
        "outcome": done.get("outcome"),
        "claims": claims,
        "sources": done.get("sources", []),
    }


if __name__ == "__main__":
    mcp.run()
