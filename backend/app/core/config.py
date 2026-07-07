from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Embeddings are hardcoded to a single model/dim (no more provider flags).
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
EMBEDDING_BATCH_SIZE = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_title: str = "Loupe"
    api_version: str = "0.2.0"
    app_env: str = "dev"

    # Providers
    gemini_api_key: str
    pinecone_api_key: str | None = None
    pinecone_index: str = "loupe"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    tavily_api_key: str | None = None

    # Observability (optional; all three enable Langfuse tracing — §9)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    # Models
    model_synth: str = "gemini-2.5-flash"
    model_control: str = "gemini-2.5-flash-lite"

    # Agent
    require_deep_approval: bool = False  # HITL gate for deep web research; prod sets 1
    threads_db_path: str = "data/threads.db"
    question_max_chars: int = 500

    # Retrieval
    hybrid_alpha: float = 0.6
    retrieve_top_k: int = 8
    chunks_path: str = "data/index/chunks.jsonl"
    corpus_path: str = "data/corpus/ai_research_corpus.json"

    # Chunking
    max_chunk_chars: int = 1200
    chunk_overlap: int = 200

    # Access / security
    # NoDecode: accept a comma-separated env value (CORS_ORIGINS=a.com,b.com) rather
    # than requiring JSON; the validator below splits it. Without this, a plain
    # comma-separated value raises SettingsError at startup.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    require_hcaptcha: bool = False
    hcaptcha_secret_key: str | None = None
    trusted_proxy: int = 0
    # Per-IP short-window burst limit.
    rate_limit_requests_per_window: int = 8
    rate_limit_window_seconds: int = 300
    # Per-IP daily cap (one client cannot exceed this many requests/day).
    daily_request_limit: int = 200
    # Aggregate daily kill-switch across ALL clients — bounds total API spend even
    # under distributed (rotating-IP) abuse. Set well above expected legit traffic.
    global_daily_request_limit: int = 2000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):  # tolerate a legacy JSON-array value
                import json

                try:
                    return json.loads(text)
                except ValueError:
                    pass
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value


settings = Settings()  # type: ignore[call-arg]  # values sourced from env / .env
