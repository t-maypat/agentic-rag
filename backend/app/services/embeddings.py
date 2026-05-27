from typing import Protocol

import google.generativeai as genai
from fastembed import TextEmbedding

from app.core.config import settings


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class GeminiEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings.")
        genai.configure(api_key=api_key)
        self.model_name = model_name

    @staticmethod
    def _extract_embedding(response: object) -> list[float]:
        if isinstance(response, dict):
            embedding = response.get("embedding")
        else:
            embedding = getattr(response, "embedding", None)
        if embedding is None:
            raise ValueError("Gemini embedding response missing embedding field.")
        return list(embedding)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            response = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document",
            )
            vectors.append(self._extract_embedding(response))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = genai.embed_content(
            model=self.model_name,
            content=text,
            task_type="retrieval_query",
        )
        return self._extract_embedding(response)


class FastEmbedProvider:
    def __init__(self, model_name: str) -> None:
        self.model = TextEmbedding(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.embed(texts)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class EmbeddingService:
    def __init__(self) -> None:
        provider = settings.embedding_provider.lower()
        if provider == "gemini":
            self.provider: EmbeddingProvider = GeminiEmbeddingProvider(
                settings.gemini_api_key,
                settings.embedding_model,
            )
        elif provider == "fastembed":
            self.provider = FastEmbedProvider(settings.embedding_model)
        else:
            raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.provider.embed_query(text)


embedding_service = EmbeddingService()
