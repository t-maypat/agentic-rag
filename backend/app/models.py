from pydantic import BaseModel, Field


class DocumentInput(BaseModel):
    doc_id: str | None = None
    title: str | None = None
    text: str
    source: str | None = None


class IngestRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)
    documents: list[DocumentInput] = Field(default_factory=list)


class IngestResponse(BaseModel):
    ingested: int
    chunks: int


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class SourceChunk(BaseModel):
    chunk_id: str
    score: float
    title: str | None = None
    source: str | None = None
    text: str


class TraceStep(BaseModel):
    name: str
    detail: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    trace: list[TraceStep]
