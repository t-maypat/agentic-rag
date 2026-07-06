from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # Models
    model_synth: str = "gemini-2.5-flash"
    model_control: str = "gemini-2.5-flash-lite"

    # Agent
    require_deep_approval: bool = False  # prod sets 1; HITL interrupt lands in Phase 3
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
    cors_origins: list[str] = ["http://localhost:5173"]
    require_hcaptcha: bool = False
    hcaptcha_secret_key: str | None = None
    trusted_proxy: int = 0
    rate_limit_requests_per_window: int = 8
    rate_limit_window_seconds: int = 300
    daily_request_limit: int = 200


settings = Settings()  # type: ignore[call-arg]  # values sourced from env / .env
