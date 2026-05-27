import hashlib
import json
from pathlib import Path

from app.core.config import settings
from app.models import DocumentInput, DocumentSection
from app.services.embeddings import embedding_service
from app.services.pinecone_client import pinecone_index
from app.services.lexical_index import LexicalChunk, upsert_chunks
from app.services.text_splitter import split_document


def _load_text_from_path(path: Path) -> list[DocumentInput]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8")
        return [
            DocumentInput(
                doc_id=path.stem,
                title=path.stem.replace("-", " ").title(),
                text=text,
                source=str(path),
                source_type="markdown" if suffix == ".md" else "text",
            )
        ]

    if suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            payload = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = [payload]
        documents = []
        for item in payload:
            authors = item.get("authors")
            if isinstance(authors, str):
                authors = [authors]
            year = item.get("year")
            if isinstance(year, str) and year.isdigit():
                year = int(year)
            sections = item.get("sections")
            parsed_sections = None
            if isinstance(sections, list):
                parsed_sections = [
                    DocumentSection(heading=section.get("heading"), text=section.get("text", ""))
                    for section in sections
                    if isinstance(section, dict)
                ]
            documents.append(
                DocumentInput(
                    doc_id=item.get("id") or item.get("doc_id") or path.stem,
                    title=item.get("title"),
                    text=item.get("text", ""),
                    source=item.get("source") or str(path),
                    authors=authors,
                    year=year,
                    source_type=item.get("source_type"),
                    url=item.get("url"),
                    sections=parsed_sections,
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
        try:
            raw_text = doc.text
            if doc.sections:
                raw_text = "\n".join(section.text for section in doc.sections)
            hash_seed = f"{doc.title or ''}\n{raw_text}\n{doc.url or ''}"
            doc_hash = hashlib.md5(hash_seed.encode("utf-8")).hexdigest()
            doc_id = doc.doc_id or f"doc-{doc_hash}"
            chunks = split_document(
                doc.text,
                doc.sections,
                settings.max_chunk_chars,
                settings.chunk_overlap,
            )
            if not chunks:
                continue

            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = embedding_service.embed_documents(chunk_texts)
            for chunk, embedding in zip(chunks, embeddings, strict=False):
                vector_id = f"{doc_id}:{chunk.chunk_index}"
                lexical_chunks.append(
                    LexicalChunk(
                        chunk_id=vector_id,
                        doc_id=doc_id,
                        title=doc.title,
                        section=chunk.section,
                        source=doc.source,
                        authors=doc.authors,
                        year=doc.year,
                        source_type=doc.source_type,
                        url=doc.url,
                        text=chunk.text,
                    )
                )
                vectors.append(
                    (
                        vector_id,
                        embedding,
                        {
                            "doc_id": doc_id,
                            "title": doc.title,
                            "section": chunk.section,
                            "source": doc.source,
                            "authors": doc.authors,
                            "year": doc.year,
                            "source_type": doc.source_type,
                            "url": doc.url,
                            "chunk_index": chunk.chunk_index,
                            "text": chunk.text,
                        },
                    )
                )
            chunk_count += len(chunks)
        except Exception as exc:  # noqa: BLE001
            doc_label = doc.doc_id or doc.title or doc.source or "unknown"
            raise RuntimeError(f"Ingest failed for {doc_label}: {exc}") from exc

    if vectors:
        pinecone_index.upsert(vectors=vectors)

    if lexical_chunks:
        upsert_chunks(Path(settings.lexical_index_path), lexical_chunks)

    return len(loaded_docs), chunk_count
