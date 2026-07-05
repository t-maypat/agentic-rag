"""Build the committed BM25 chunk index from the corpus (offline, no network).

Reads ``data/corpus/ai_research_corpus.json`` and writes
``data/index/chunks.jsonl`` using the same deterministic chunking + id scheme as
the retrieval pipeline. Run this whenever the corpus changes:

    uv run python scripts/build_chunks.py
"""

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.models import DocumentSection  # noqa: E402
from app.retrieval.chunking import split_document  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_sections(raw: object) -> list[DocumentSection] | None:
    if not isinstance(raw, list):
        return None
    return [
        DocumentSection(heading=item.get("heading"), text=item.get("text", ""))
        for item in raw
        if isinstance(item, dict)
    ]


def main() -> None:
    corpus_path = REPO_ROOT / settings.corpus_path
    out_path = REPO_ROOT / settings.chunks_path
    if not corpus_path.exists():
        raise SystemExit(f"Corpus not found: {corpus_path}")

    documents = json.loads(corpus_path.read_text(encoding="utf-8"))
    if isinstance(documents, dict):
        documents = [documents]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for doc in documents:
            doc_id = doc.get("id") or doc.get("doc_id")
            title = doc.get("title")
            sections = _parse_sections(doc.get("sections"))
            chunks = split_document(
                doc.get("text", ""),
                sections,
                settings.max_chunk_chars,
                settings.chunk_overlap,
            )
            for chunk in chunks:
                record = {
                    "chunk_id": f"{doc_id}:{chunk.chunk_index}",
                    "doc_id": doc_id,
                    "title": title,
                    "section": chunk.section,
                    "source": doc.get("source"),
                    "authors": doc.get("authors"),
                    "year": doc.get("year"),
                    "source_type": doc.get("source_type"),
                    "url": doc.get("url"),
                    "text": chunk.text,
                }
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
                total += 1

    print(f"Wrote {total} chunks from {len(documents)} documents -> {out_path}")


if __name__ == "__main__":
    main()
