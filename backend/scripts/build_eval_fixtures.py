"""Build committed embedding fixtures for the offline retrieval eval (§8.2, §16).

Embeds every corpus chunk (``data/index/chunks.jsonl``) and every golden-retrieval
question with ``gemini-embedding-001`` and writes:

    data/eval/fixtures/corpus_embeddings.npz   (ids, vectors, meta)
    data/eval/fixtures/query_embeddings.npz    (qids, vectors, meta)

Each file records a drift-guard signature (corpus version + golden-question hash)
so the eval fails loudly when the corpus or questions change without regeneration.

Requires GEMINI_API_KEY. Run only when the corpus or golden questions change:

    uv run python scripts/build_eval_fixtures.py
"""

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import EMBEDDING_MODEL, settings  # noqa: E402
from app.eval.datasets import (  # noqa: E402
    corpus_version,
    load_golden_retrieval,
    questions_signature,
)
from app.services.embeddings import GeminiEmbeddingProvider  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = REPO_ROOT / settings.chunks_path
GOLDEN_RETRIEVAL = REPO_ROOT / "data/eval/golden_retrieval.jsonl"
FIXTURE_DIR = REPO_ROOT / "data/eval/fixtures"


def _load_chunks() -> tuple[list[str], list[str]]:
    ids: list[str] = []
    texts: list[str] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                payload = json.loads(line)
                ids.append(payload["chunk_id"])
                texts.append(payload.get("text", ""))
    return ids, texts


def main() -> None:
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is required to build eval fixtures.")

    provider = GeminiEmbeddingProvider(settings.gemini_api_key, EMBEDDING_MODEL)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    version = corpus_version(CHUNKS_PATH)
    now = dt.datetime.now(dt.UTC).isoformat()

    # Corpus embeddings (RETRIEVAL_DOCUMENT).
    ids, texts = _load_chunks()
    print(f"Embedding {len(texts)} corpus chunks…")
    corpus_vectors = np.asarray(provider.embed_documents(texts), dtype=np.float32)
    corpus_meta = {
        "corpus_version": version,
        "model": EMBEDDING_MODEL,
        "dim": corpus_vectors.shape[1],
        "built_at": now,
    }
    np.savez_compressed(
        FIXTURE_DIR / "corpus_embeddings.npz",
        ids=np.array(ids, dtype=object),
        vectors=corpus_vectors,
        meta=json.dumps(corpus_meta),
    )

    # Query embeddings (RETRIEVAL_QUERY) — golden-retrieval questions only.
    items = load_golden_retrieval(GOLDEN_RETRIEVAL)
    qids = [item["qid"] for item in items]
    questions = [item["question"] for item in items]
    print(f"Embedding {len(questions)} golden-retrieval questions…")
    query_vectors = np.asarray(
        [provider.embed_query(question) for question in questions], dtype=np.float32
    )
    query_meta = {
        "corpus_version": version,
        "questions_signature": questions_signature(questions),
        "model": EMBEDDING_MODEL,
        "dim": query_vectors.shape[1],
        "built_at": now,
    }
    np.savez_compressed(
        FIXTURE_DIR / "query_embeddings.npz",
        qids=np.array(qids, dtype=object),
        vectors=query_vectors,
        meta=json.dumps(query_meta),
    )

    print(f"Wrote fixtures to {FIXTURE_DIR} (corpus_version={version}).")


if __name__ == "__main__":
    main()
