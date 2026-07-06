"""Synthesize: assemble context (§3.3), then stream a cited markdown answer."""

import time
from typing import Any

from app.agent import events
from app.agent.deps import NodeConfig, get_deps
from app.agent.state import EvidenceChunk, ResearchState
from app.prompts import registry

_MAX_SOURCES = 10


def _fused(chunk: EvidenceChunk) -> float:
    return float(chunk.scores.get("fused") or 0.0)


def _select_sources(state: ResearchState) -> list[EvidenceChunk]:
    """Round-robin across sub-questions, best fused chunk each pass, ≤ 10 total.

    Sufficient sub-questions are pooled first; insufficient ones contribute
    best-effort chunks (reached only when the rewrite budget is spent). Low-trust
    chunks are excluded (Phase 3 flags them; kept here for forward-compat)."""
    grades = state["grades"]
    ordered_sqs = sorted(
        state["sub_questions"],
        key=lambda sq: 0 if (grades.get(sq.id) and grades[sq.id].sufficient) else 1,
    )
    lists: list[list[EvidenceChunk]] = []
    for sq in ordered_sqs:
        chunks = [c for c in state["evidence"].get(sq.id, []) if c.trust != "low"]
        chunks.sort(key=_fused, reverse=True)
        lists.append(chunks)

    selected: list[EvidenceChunk] = []
    seen: set[str] = set()
    pointers = [0] * len(lists)
    progressed = True
    while len(selected) < _MAX_SOURCES and progressed:
        progressed = False
        for i, chunks in enumerate(lists):
            while pointers[i] < len(chunks) and chunks[pointers[i]].id in seen:
                pointers[i] += 1
            if pointers[i] < len(chunks):
                chunk = chunks[pointers[i]]
                pointers[i] += 1
                seen.add(chunk.id)
                selected.append(chunk)
                progressed = True
                if len(selected) >= _MAX_SOURCES:
                    break
    return selected


def _render_evidence(sources: list[EvidenceChunk]) -> str:
    blocks: list[str] = []
    for chunk in sources:
        section = f" — {chunk.section}" if chunk.section else ""
        header = f"[{chunk.source_id}] {chunk.doc_title}{section} ({chunk.origin})"
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def synthesize(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    started = time.monotonic()
    events.stage_start("synthesize")
    deps = get_deps(config)

    selected = _select_sources(state)
    if not selected:
        events.stage_end(
            "synthesize", "no evidence → refusal", int((time.monotonic() - started) * 1000)
        )
        return {"sources": [], "draft_answer": None}

    sources = [
        chunk.model_copy(update={"source_id": f"S{i}"}) for i, chunk in enumerate(selected, 1)
    ]

    prompt = registry.get("synthesize")
    rendered = prompt.render(
        question=state["standalone_question"], evidence_block=_render_evidence(sources)
    )

    parts: list[str] = []
    for token in deps.llm.generate_stream(
        rendered,
        ledger=state["ledger"],
        role=prompt.model_role,
        temperature=prompt.temperature,
        prompt_id=prompt.tag,
    ):
        parts.append(token)
        events.emit(events.TOKEN, text=token)

    draft = "".join(parts).strip()
    events.stage_end(
        "synthesize",
        f"{len(sources)} sources, {len(draft)} chars",
        int((time.monotonic() - started) * 1000),
    )
    return {"sources": sources, "draft_answer": draft or None}
