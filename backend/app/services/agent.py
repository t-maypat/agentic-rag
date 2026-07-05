from app.core.config import settings
from app.models import QueryResponse, SourceChunk, TraceStep
from app.services.llm import generate_answer
from app.services.retrieval import RetrievalResult, retrieve_chunks


def _format_authors(authors: list[str] | None) -> str | None:
    if not authors:
        return None
    if len(authors) <= 2:
        return ", ".join(authors)
    return f"{authors[0]} et al."


def _format_meta(chunk: SourceChunk) -> str:
    parts = [
        chunk.title,
        chunk.section,
        _format_authors(chunk.authors),
        str(chunk.year) if chunk.year else None,
        chunk.source_type,
        chunk.source,
    ]
    meta = " | ".join(filter(None, parts))
    if chunk.url:
        meta = f"{meta} | {chunk.url}" if meta else chunk.url
    return meta


def _build_context(chunks: list[SourceChunk]) -> str:
    blocks = []
    for idx, chunk in enumerate(chunks, start=1):
        label = f"Source {idx}"
        meta = _format_meta(chunk)
        header = f"{label} ({meta})" if meta else label
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def _truncate(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}... [truncated, {len(text)} chars]"


def _format_candidates(chunks: list[SourceChunk], mode: str) -> str:
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        meta = _format_meta(chunk)
        if mode == "dense":
            score = chunk.dense_score or 0.0
            norm = chunk.dense_score_norm or 0.0
            score_label = f"dense={score:.4f} norm={norm:.3f}"
        elif mode == "bm25":
            score = chunk.bm25_score or 0.0
            norm = chunk.bm25_score_norm or 0.0
            score_label = f"bm25={score:.4f} norm={norm:.3f}"
        else:
            score_label = (
                f"hybrid={chunk.score:.3f} | dense={chunk.dense_score_norm or 0.0:.3f} "
                f"bm25={chunk.bm25_score_norm or 0.0:.3f}"
            )
        label = meta or "Untitled source"
        lines.append(f"{idx}. {label} ({score_label}) [id={chunk.chunk_id}]")
    return "\n".join(lines) if lines else "No candidates."


def answer_question(query: str, top_k: int) -> QueryResponse:
    trace: list[TraceStep] = []

    trace.append(TraceStep(name="query", detail=f"User query: {query}"))
    result: RetrievalResult = retrieve_chunks(query, top_k)
    diagnostics = result.diagnostics

    trace.append(
        TraceStep(
            name="dense_retrieval",
            detail=_format_candidates(diagnostics.dense_candidates, "dense"),
        )
    )

    trace.append(
        TraceStep(
            name="bm25_retrieval",
            detail=_format_candidates(diagnostics.lexical_candidates, "bm25"),
        )
    )
    trace.append(
        TraceStep(
            name="fusion",
            detail=_format_candidates(diagnostics.fused_candidates, "hybrid"),
        )
    )

    chunks = result.chunks
    trace.append(
        TraceStep(
            name="selected_chunks",
            detail=_format_candidates(chunks, "hybrid"),
        )
    )

    context = _build_context(chunks)
    system_prompt = (
        "You are a precise AI research assistant. Use the provided sources to answer the question. "
        "If the sources are insufficient, state what is missing. Cite sources as [1], [2]."
    )
    user_prompt = (
        f"Question: {query}\n\n"
        f"Sources:\n{context}\n\n"
        "Answer with clear bullets and citations."
    )

    trace.append(
        TraceStep(
            name="prompt",
            detail=_truncate(f"System prompt:\n{system_prompt}\n\nUser prompt:\n{user_prompt}"),
        )
    )

    answer = generate_answer(system_prompt, user_prompt)
    trace.append(
        TraceStep(
            name="generation",
            detail=f"Model={settings.model_synth} | Provider=gemini",
        )
    )

    return QueryResponse(answer=answer, sources=chunks, trace=trace)
