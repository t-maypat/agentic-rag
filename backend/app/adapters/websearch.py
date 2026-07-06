"""Web search port + adapters (REVAMP_PLAN §4.2, §5.2).

``WebSearch`` is the seam the retrieve node sees. :class:`TavilySearch` is the
real adapter (constructed only when ``TAVILY_API_KEY`` is set); :class:`NullSearch`
is the disabled stand-in so Deep mode degrades gracefully to corpus-only. Both
return domain :class:`EvidenceChunk` values, never SDK types.

Every raw result is passed through the sanitizer (:mod:`app.security.sanitize`)
before it becomes evidence, so untrusted web text is stripped, truncated, and
injection-flagged at the boundary — not inside a node.
"""

import hashlib
from typing import Any, Protocol

from app.agent.state import EvidenceChunk
from app.security import sanitize

# Tavily free tier defaults (§4.2): raw content, at most 3 results per query.
DEFAULT_MAX_RESULTS = 3


def _web_id(url: str, index: int) -> str:
    digest = hashlib.sha256((url or f"web-{index}").encode("utf-8")).hexdigest()[:16]
    return f"web-{digest}"


def result_to_evidence(result: dict[str, Any], index: int) -> EvidenceChunk:
    """Map one Tavily result dict to a sanitized :class:`EvidenceChunk`.

    Pure and side-effect free so it is unit-tested with hostile fixtures.
    """
    url = result.get("url") or ""
    raw = result.get("raw_content") or result.get("content") or ""
    text = sanitize.sanitize_web_text(raw)
    trust = "low" if sanitize.flag_injection(text) else "normal"
    score = float(result.get("score") or 0.0)
    return EvidenceChunk(
        id=_web_id(url, index),
        doc_title=result.get("title") or url or "Web result",
        section=None,
        url=url or None,
        text=text,
        origin="web",
        scores={"dense": None, "bm25": None, "fused": score},
        trust=trust,
    )


class WebSearch(Protocol):
    available: bool

    def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[EvidenceChunk]: ...


class NullSearch:
    """Disabled web tool: reports unavailable and returns no evidence."""

    available = False

    def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[EvidenceChunk]:
        return []


class TavilySearch:
    """Tavily adapter implementing :class:`WebSearch` (§4.2)."""

    available = True

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required for TavilySearch.")
        from tavily import TavilyClient

        self._client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[EvidenceChunk]:
        response = self._client.search(
            query=query,
            max_results=max_results,
            include_raw_content=True,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        return [result_to_evidence(result, i) for i, result in enumerate(results)]


def build_web_search(api_key: str | None) -> WebSearch:
    """Return the Tavily adapter when a key is configured, else the null tool."""
    if api_key:
        return TavilySearch(api_key)
    return NullSearch()
