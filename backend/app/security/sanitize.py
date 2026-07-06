"""Prompt-injection defense for web content (REVAMP_PLAN §10.2).

Web results are untrusted data. Before any web text reaches an LLM prompt it is:

1. Stripped from HTML to plain text (trafilatura, with a raw-text fallback) and
   truncated to :data:`MAX_WEB_CHARS` characters.
2. Scanned by :func:`flag_injection` for high-signal injection phrases; a hit marks
   the chunk ``trust="low"`` so synthesis excludes it (it stays visible in the
   evidence drawer).
3. Wrapped in ``<web_evidence source="...">`` tags by :func:`wrap_web_evidence`
   when rendered into a prompt, so the model can be told the enclosed content is
   untrusted and must never be followed as instructions.

Pure functions, no network — unit-tested directly.
"""

import re

MAX_WEB_CHARS = 3_000

# High-signal prompt-injection phrases. Matched case-insensitively against the
# extracted text; any hit flags the chunk as low trust.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+|the\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+|the\s+)?(previous|prior|above)",
        r"forget\s+(everything|all|the\s+above)",
        r"system\s+prompt",
        r"you\s+are\s+now\b",
        r"new\s+instructions?\s*:",
        r"reveal\s+your\s+(system\s+prompt|instructions)",
        r"</?\s*(system|assistant)\s*>",
    )
)

_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def sanitize_web_text(raw: str, limit: int = MAX_WEB_CHARS) -> str:
    """Extract readable text from an HTML/raw web result and truncate it.

    trafilatura handles real HTML; when the input is already plain text (Tavily's
    ``raw_content`` often is) extraction returns nothing, so we fall back to the
    raw string. Whitespace is collapsed and the result capped at ``limit`` chars.
    """
    text = ""
    stripped = (raw or "").strip()
    if "<" in stripped and ">" in stripped:
        # Only pay for HTML extraction when it plausibly is HTML.
        import trafilatura

        extracted = trafilatura.extract(stripped) or ""
        text = extracted.strip()
    if not text:
        text = stripped
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text[:limit].strip()


def flag_injection(text: str) -> bool:
    """Return True if the text contains a high-signal prompt-injection phrase."""
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def wrap_web_evidence(text: str, source: str | None) -> str:
    """Wrap untrusted web text in a labelled tag for prompt rendering."""
    src = (source or "unknown").replace('"', "'")
    return f'<web_evidence source="{src}">\n{text}\n</web_evidence>'
