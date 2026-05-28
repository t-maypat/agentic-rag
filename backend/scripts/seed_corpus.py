import sys
from pathlib import Path

import httpx

# Ensure backend package is importable when running from repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings


API_BASE = "http://localhost:8000"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    corpus_path = root / settings.corpus_manifest_path
    if not corpus_path.exists():
        raise SystemExit(f"Corpus manifest not found: {corpus_path}")

    payload = {"paths": [str(corpus_path)], "documents": []}
    response = httpx.post(f"{API_BASE}/ingest", json=payload, timeout=120)
    if not response.is_success:
        print(f"Ingest failed: {response.status_code}\n{response.text}")
        response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
