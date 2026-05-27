from pathlib import Path

import httpx

from app.core.config import settings


API_BASE = "http://localhost:8000"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    corpus_path = root / settings.corpus_manifest_path
    if not corpus_path.exists():
        raise SystemExit(f"Corpus manifest not found: {corpus_path}")

    payload = {"paths": [str(corpus_path)], "documents": []}
    response = httpx.post(f"{API_BASE}/ingest", json=payload, timeout=120)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
