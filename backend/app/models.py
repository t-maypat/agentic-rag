from pydantic import BaseModel


class DocumentSection(BaseModel):
    heading: str | None = None
    text: str


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    hcaptcha_token: str | None = None


class SourceChunk(BaseModel):
    chunk_id: str
    score: float
    doc_id: str | None = None
    title: str | None = None
    section: str | None = None
    source: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    source_type: str | None = None
    url: str | None = None
    dense_score: float | None = None
    dense_score_norm: float | None = None
    bm25_score: float | None = None
    bm25_score_norm: float | None = None
    text: str


class TraceStep(BaseModel):
    name: str
    detail: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    trace: list[TraceStep]
