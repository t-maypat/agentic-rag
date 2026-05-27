from app.core.config import settings
from app.models import QueryResponse, SourceChunk, TraceStep
from app.services.llm import generate_answer
from app.services.retrieval import retrieve_chunks


def _build_context(chunks: list[SourceChunk]) -> str:
    blocks = []
    for idx, chunk in enumerate(chunks, start=1):
        label = f"Source {idx}"
        meta = " | ".join(filter(None, [chunk.title, chunk.source]))
        header = f"{label} ({meta})" if meta else label
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def answer_question(query: str, top_k: int) -> QueryResponse:
    trace: list[TraceStep] = []

    mode = "hybrid" if settings.hybrid_search_enabled else "vector"
    trace.append(TraceStep(name="retrieve", detail=f"Searching top {top_k} chunks ({mode})"))
    chunks = retrieve_chunks(query, top_k)

    context = _build_context(chunks)
    trace.append(TraceStep(name="synthesize", detail=f"Synthesizing answer from {len(chunks)} chunks"))

    system_prompt = (
        "You are a precise research assistant. Use the provided sources to answer the question. "
        "If the sources are insufficient, say what is missing. Cite sources as [1], [2]."
    )
    user_prompt = (
        f"Question: {query}\n\n"
        f"Sources:\n{context}\n\n"
        "Answer with clear bullets and citations."
    )

    answer = generate_answer(system_prompt, user_prompt)

    return QueryResponse(answer=answer, sources=chunks, trace=trace)
