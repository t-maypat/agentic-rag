from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    api_title: str = "Research RAG Studio"
    api_version: str = "0.1.0"

    llm_provider: str = "gemini"
    llm_model: str = "gemini-1.5-pro"
    gemini_api_key: str

    pinecone_api_key: str
    pinecone_index: str = "research-rag"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    embedding_batch_size: int = 32

    max_chunk_chars: int = 1200
    chunk_overlap: int = 200

    hybrid_search_enabled: bool = True
    hybrid_alpha: float = 0.7
    bm25_k: int = 10
    lexical_index_path: str = "backend/data/lexical_index.jsonl"
    corpus_manifest_path: str = "data/corpus/ai_research_corpus.json"

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
