"""Golden-dataset loaders and content hashing (REVAMP_PLAN §8.1, §16).

The retrieval and generation datasets are hand-curated JSONL committed under
``data/eval/``. The hashing helpers back the fixture drift guard: embeddings must
be regenerated whenever the corpus or the golden questions change.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

RETRIEVAL_CATEGORIES = (
    "definitional",
    "comparative",
    "specific-fact",
    "multi-hop",
    "unanswerable-from-corpus",
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_golden_retrieval(path: Path) -> list[dict[str, Any]]:
    return _load_jsonl(path)


def load_golden_generation(path: Path) -> list[dict[str, Any]]:
    return _load_jsonl(path)


def corpus_version(chunks_path: Path) -> str:
    """sha256[:16] of the chunk index — same scheme as ``app.retrieval.index``."""
    digest = hashlib.sha256()
    with chunks_path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def questions_signature(questions: list[str]) -> str:
    """Order-sensitive hash of golden-retrieval question texts (drift guard)."""
    digest = hashlib.sha256()
    for question in questions:
        digest.update(question.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]
