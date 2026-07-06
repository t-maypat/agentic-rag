"""Verify: audit each claim in the drafted answer against its cited evidence.

The differentiator (REVAMP_PLAN §3.4). The draft is segmented into atomic claims
(:mod:`app.agent.segment`); one batched structured-output call returns a verdict
per claim. Claim ids are validated against the request (mismatch → refusal, never
a silent wrong verdict). Uncited factual claims are capped at ``PARTIAL``.
"""

import time
from typing import Any

from app.agent import events
from app.agent.deps import NodeConfig, get_deps
from app.agent.errors import NodeOutputError
from app.agent.schemas import VerifyResult
from app.agent.segment import cited_source_ids, segment_claims
from app.agent.state import ClaimAudit, EvidenceChunk, ResearchState
from app.prompts import registry


def _render_evidence(sources: list[EvidenceChunk]) -> str:
    blocks: list[str] = []
    for chunk in sources:
        section = f" — {chunk.section}" if chunk.section else ""
        header = f"[{chunk.source_id}] {chunk.doc_title}{section} ({chunk.origin})"
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def _render_claims(claim_texts: list[str], valid_ids: set[str]) -> str:
    lines: list[str] = []
    for i, text in enumerate(claim_texts, 1):
        cited = [sid for sid in cited_source_ids(text) if sid in valid_ids]
        marker = ",".join(cited) if cited else "none"
        lines.append(f"[c{i}] (cites: {marker}) {text}")
    return "\n".join(lines)


def _audit(
    claim_texts: list[str], result: VerifyResult, valid_ids: set[str], sources: list[EvidenceChunk]
) -> list[ClaimAudit]:
    expected = [f"c{i}" for i in range(1, len(claim_texts) + 1)]
    by_id = {row.id: row for row in result.claims}
    if set(by_id) != set(expected) or len(result.claims) != len(expected):
        raise NodeOutputError("verify: judge verdicts do not match the audited claims")

    all_ids = [chunk.source_id for chunk in sources]
    claims: list[ClaimAudit] = []
    for cid, text in zip(expected, claim_texts, strict=True):
        cited = [sid for sid in cited_source_ids(text) if sid in valid_ids]
        verdict = by_id[cid].verdict
        # An uncited factual claim can never be SUPPORTED (§3.4).
        if not cited and verdict == "SUPPORTED":
            verdict = "PARTIAL"
        claims.append(
            ClaimAudit(
                id=cid,
                text=text,
                verdict=verdict,
                evidence_ids=cited or all_ids,
                note=by_id[cid].note,
            )
        )
    return claims


def verify(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    started = time.monotonic()
    events.stage_start("verify")
    deps = get_deps(config)

    draft = state.get("draft_answer")
    sources = state.get("sources") or []
    if not draft or not sources:
        events.stage_end("verify", "no draft → skip", int((time.monotonic() - started) * 1000))
        return {"claims": []}

    claim_texts = segment_claims(draft)
    if not claim_texts:
        events.stage_end("verify", "no claims segmented", int((time.monotonic() - started) * 1000))
        return {"claims": []}

    valid_ids = {chunk.source_id for chunk in sources}
    prompt = registry.get("verify")
    rendered = prompt.render(
        claims_block=_render_claims(claim_texts, valid_ids),
        evidence_block=_render_evidence(sources),
    )

    try:
        result = deps.llm.generate_json(
            rendered,
            VerifyResult,
            ledger=state["ledger"],
            role=prompt.model_role,
            temperature=prompt.temperature,
            prompt_id=prompt.tag,
        )
        claims = _audit(claim_texts, result, valid_ids, sources)
    except NodeOutputError:
        # Can't audit reliably → refuse rather than present unchecked claims (§4.3).
        events.stage_end(
            "verify", "audit failed → refuse", int((time.monotonic() - started) * 1000)
        )
        return {"claims": [], "outcome": "refused"}

    events.emit(events.CLAIMS, claims=[claim.model_dump() for claim in claims])
    unsupported = sum(1 for claim in claims if claim.verdict == "UNSUPPORTED")
    events.stage_end(
        "verify",
        f"{len(claims)} claims, {unsupported} unsupported",
        int((time.monotonic() - started) * 1000),
    )
    return {"claims": claims}
