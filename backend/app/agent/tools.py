"""Agent tools. Phase 1 ships the corpus retrieval tool only.

``search_corpus`` wraps the existing hybrid (dense Pinecone + BM25) retrieval and
maps the impure ``SourceChunk`` results into the agent's ``EvidenceChunk`` domain
type. The web tool (Tavily) lands in Phase 3.
"""

from app.agent.state import EvidenceChunk
from app.core.config import settings
from app.models import SourceChunk


def _to_evidence(chunk: SourceChunk) -> EvidenceChunk:
    return EvidenceChunk(
        id=chunk.chunk_id,
        doc_title=chunk.title or chunk.doc_id or "Untitled",
        section=chunk.section,
        url=chunk.url,
        text=chunk.text,
        origin="corpus",
        scores={
            "dense": chunk.dense_score_norm,
            "bm25": chunk.bm25_score_norm,
            "fused": chunk.score,
        },
    )


def search_corpus(query: str, top_k: int = 8) -> list[EvidenceChunk]:
    # Imported lazily so tests that inject a fake tool never import Pinecone.
    from app.services.retrieval import retrieve_chunks

    result = retrieve_chunks(query, top_k or settings.retrieve_top_k)
    return [_to_evidence(chunk) for chunk in result.chunks]
