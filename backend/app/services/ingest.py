import hashlib
import json
from pathlib import Path

from app.core.config import settings
from app.models import DocumentInput
from app.services.embeddings import embedding_service
from app.services.pinecone_client import pinecone_index
from app.services.lexical_index import LexicalChunk, upsert_chunks
from app.services.text_splitter import split_text


def _load_text_from_path(path: Path) -> list[DocumentInput]:
    if path.suffix.lower() in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8")
        return [
            DocumentInput(
                doc_id=path.stem,
                title=path.stem.replace("-", " ").title(),
                text=text,
                source=str(path),
            )
        ]

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = [payload]
        documents = []
        for item in payload:
            documents.append(
                DocumentInput(
                    doc_id=item.get("id") or item.get("doc_id") or path.stem,
                    title=item.get("title"),
                    text=item.get("text", ""),
                    source=item.get("source") or str(path),
                )
            )
        return documents

    return []


def ingest_documents(paths: list[str], documents: list[DocumentInput]) -> tuple[int, int]:
    loaded_docs = list(documents)

    for raw_path in paths:
        path = Path(raw_path)
        if path.exists():
            loaded_docs.extend(_load_text_from_path(path))

    vectors = []
    lexical_chunks: list[LexicalChunk] = []
    chunk_count = 0

    for doc in loaded_docs:
        doc_hash = hashlib.md5(doc.text.encode("utf-8")).hexdigest()
        doc_id = doc.doc_id or f"doc-{doc_hash}"
        chunks = split_text(doc.text, settings.max_chunk_chars, settings.chunk_overlap)
        if not chunks:
            continue

        embeddings = embedding_service.embed_texts(chunks)
        for index, chunk in enumerate(chunks):
            vector_id = f"{doc_id}:{index}"
            lexical_chunks.append(
                LexicalChunk(
                    chunk_id=vector_id,
                    title=doc.title,
                    source=doc.source,
                    text=chunk,
                )
            )
            vectors.append(
                (
                    vector_id,
                    embeddings[index],
                    {
                        "doc_id": doc_id,
                        "title": doc.title,
                        "source": doc.source,
                        "chunk_index": index,
                        "text": chunk,
                    },
                )
            )
        chunk_count += len(chunks)

    if vectors:
        pinecone_index.upsert(vectors=vectors)

    if lexical_chunks:
        upsert_chunks(Path(settings.lexical_index_path), lexical_chunks)

    return len(loaded_docs), chunk_count
