"""Retrieve: run the corpus tool for each pending/insufficient sub-question.

Quick mode has no plan step, so retrieve synthesizes the single implicit
sub-question ``sq1 = standalone_question`` on first entry.
"""

import time
from typing import Any

from app.agent import events
from app.agent.deps import NodeConfig, get_deps
from app.agent.state import EvidenceChunk, ResearchState, SubQuestion
from app.core.config import settings

_EVIDENCE_TEXT_LIMIT = 400


def _chunk_lite(chunk: EvidenceChunk) -> dict[str, Any]:
    text = chunk.text
    if len(text) > _EVIDENCE_TEXT_LIMIT:
        text = text[:_EVIDENCE_TEXT_LIMIT].rstrip() + "…"
    return {
        "id": chunk.id,
        "doc_title": chunk.doc_title,
        "section": chunk.section,
        "url": chunk.url,
        "origin": chunk.origin,
        "scores": chunk.scores,
        "trust": chunk.trust,
        "text": text,
    }


def retrieve(state: ResearchState, config: NodeConfig) -> dict[str, Any]:
    started = time.monotonic()
    iteration = state["rewrite_count"]
    events.stage_start("retrieve", iteration=iteration)
    deps = get_deps(config)

    sub_questions = list(state["sub_questions"])
    if not sub_questions:
        sub_questions = [SubQuestion(id="sq1", text=state["standalone_question"])]

    evidence = dict(state["evidence"])
    processed = 0
    for sq in sub_questions:
        if sq.status not in ("pending", "insufficient"):
            continue
        chunks = deps.search_corpus(sq.text, settings.retrieve_top_k)
        evidence[sq.id] = chunks
        processed += 1
        events.emit(
            events.EVIDENCE,
            sub_question_id=sq.id,
            chunks=[_chunk_lite(chunk) for chunk in chunks],
        )

    total = sum(len(chunks) for chunks in evidence.values())
    events.stage_end(
        "retrieve",
        f"{processed} sub-question(s), {total} chunks",
        int((time.monotonic() - started) * 1000),
        iteration=iteration,
    )
    return {"sub_questions": sub_questions, "evidence": evidence}
