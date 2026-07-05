from google import genai
from google.genai import types

from app.core.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    settings,
)


class GeminiEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.output_dimensionality = EMBEDDING_DIM
        self.batch_size = EMBEDDING_BATCH_SIZE

    @staticmethod
    def _extract_values(embedding: object) -> list[float]:
        if isinstance(embedding, dict):
            values = embedding.get("values") or embedding.get("embedding")
        else:
            values = getattr(embedding, "values", None) or getattr(embedding, "embedding", None)
        if values is None:
            raise ValueError("Gemini embedding response missing vector values.")
        return list(values)

    def _extract_embeddings(self, response: object) -> list[list[float]]:
        if isinstance(response, dict):
            embeddings = response.get("embeddings")
            if embeddings is None and response.get("embedding") is not None:
                embeddings = [response["embedding"]]
        else:
            embeddings = getattr(response, "embeddings", None)
            if embeddings is None:
                single = getattr(response, "embedding", None)
                embeddings = [single] if single is not None else None
        if not embeddings:
            raise ValueError("Gemini embedding response missing embeddings.")
        return [self._extract_values(item) for item in embeddings]

    def embed_documents(
        self, texts: list[str], titles: list[str | None] | None = None
    ) -> list[list[float]]:
        if not texts:
            return []
        resolved_titles: list[str | None] = (
            list(titles) if titles is not None else [None] * len(texts)
        )

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch_texts = texts[start : start + self.batch_size]
            batch_titles = resolved_titles[start : start + self.batch_size]
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=batch_texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    title=batch_titles[0] if len(batch_texts) == 1 else None,
                    output_dimensionality=self.output_dimensionality,
                ),
            )
            batch_vectors = self._extract_embeddings(response)
            if len(batch_vectors) != len(batch_texts):
                raise ValueError("Gemini embedding response count did not match the request.")
            vectors.extend(batch_vectors)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.output_dimensionality,
            ),
        )
        return self._extract_embeddings(response)[0]


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = GeminiEmbeddingProvider(settings.gemini_api_key, EMBEDDING_MODEL)

    def embed_documents(
        self, texts: list[str], titles: list[str | None] | None = None
    ) -> list[list[float]]:
        return self.provider.embed_documents(texts, titles)

    def embed_query(self, text: str) -> list[float]:
        return self.provider.embed_query(text)


embedding_service = EmbeddingService()
