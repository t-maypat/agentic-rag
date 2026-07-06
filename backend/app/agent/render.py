"""Shared evidence-block rendering for prompts.

Corpus and web chunks are rendered as ``[Sn] title — section (origin)`` blocks.
Web chunks are additionally wrapped in ``<web_evidence>`` tags (REVAMP_PLAN §3.3
rule 4 / §10.2) so the synthesize, grade, and verify prompts can flag the enclosed
text as untrusted data that must never be followed as instructions.
"""

from app.agent.state import EvidenceChunk
from app.security.sanitize import wrap_web_evidence


def render_source_block(chunk: EvidenceChunk) -> str:
    section = f" — {chunk.section}" if chunk.section else ""
    header = f"[{chunk.source_id}] {chunk.doc_title}{section} ({chunk.origin})"
    body = chunk.text
    if chunk.origin == "web":
        body = wrap_web_evidence(body, chunk.url)
    return f"{header}\n{body}"


def render_evidence(sources: list[EvidenceChunk]) -> str:
    return "\n\n".join(render_source_block(chunk) for chunk in sources)
