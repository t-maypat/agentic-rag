"""Claim segmentation for the verify node (REVAMP_PLAN §3.4).

Pure, network-free logic so the three tricky cases — prose, markdown lists, and
code blocks — are unit-tested directly. Rules:

- Fenced code blocks (```) are never audited and are dropped entirely.
- Each markdown list item is exactly one claim (never merged, even if short).
- Prose is split on sentence boundaries; a fragment shorter than 8 words is
  merged into the preceding claim (a leading fragment with nothing before it
  stays on its own).
- Heading-only lines (``#``…) are not factual claims and are dropped.
"""

import re

_MIN_WORDS = 8

_FENCE = re.compile(r"^\s*```")
_HEADING = re.compile(r"^\s*#{1,6}\s")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
# Split after sentence punctuation only when the next token looks like a new
# sentence (uppercase/digit/quote/citation), which avoids splitting on "e.g.".
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\[])")
_MARKER = re.compile(r"\[S(\d+)\]")


def _word_count(text: str) -> int:
    return len(text.split())


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]


def segment_claims(draft: str) -> list[str]:
    """Segment a synthesized markdown answer into ordered atomic claims."""
    units: list[tuple[str, bool]] = []  # (text, atomic) — atomic = list item
    prose: list[str] = []
    in_code = False

    def flush_prose() -> None:
        text = " ".join(prose).strip()
        prose.clear()
        for sentence in _split_sentences(text):
            units.append((sentence, False))

    for line in draft.splitlines():
        if _FENCE.match(line):
            in_code = not in_code
            flush_prose()
            continue
        if in_code:
            continue
        if _HEADING.match(line):
            flush_prose()
            continue
        item = _LIST_ITEM.match(line)
        if item:
            flush_prose()
            text = item.group(1).strip()
            if text:
                units.append((text, True))
            continue
        if line.strip():
            prose.append(line.strip())
        else:
            flush_prose()  # blank line ends a paragraph
    flush_prose()

    claims: list[str] = []
    for text, atomic in units:
        if not atomic and _word_count(text) < _MIN_WORDS and claims:
            claims[-1] = f"{claims[-1]} {text}"
        else:
            claims.append(text)
    return claims


def cited_source_ids(claim: str) -> list[str]:
    """Return the distinct ``Sn`` labels cited in a claim, in first-seen order."""
    seen: dict[str, None] = {}
    for match in _MARKER.finditer(claim):
        seen.setdefault(f"S{match.group(1)}", None)
    return list(seen)
