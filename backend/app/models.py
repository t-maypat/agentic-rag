from typing import Literal

from pydantic import BaseModel, Field


class DocumentSection(BaseModel):
    heading: str | None = None
    text: str


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    mode: Literal["quick", "deep"] = "quick"
    thread_id: str | None = None
    captcha_token: str | None = None


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
