"""Exact-match response cache (REVAMP_PLAN §5.4).

Keyed by ``sha256(normalized_question + mode + corpus_version)``. A hit replays as
a single SSE burst with ``cached: true`` in the ``done`` event. In-memory only
(single-instance demo); LRU-capped with a TTL. No semantic caching (a non-goal).
"""

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

_TTL_SECONDS = 3600.0
_MAX_ENTRIES = 256


@dataclass(frozen=True)
class CachedResponse:
    answer_md: str | None
    outcome: str
    sources: list[dict[str, Any]]
    usage: dict[str, Any]


def make_key(question: str, mode: str, corpus_version: str) -> str:
    normalized = " ".join(question.strip().lower().split())
    return hashlib.sha256(f"{normalized}\x1f{mode}\x1f{corpus_version}".encode()).hexdigest()


class ResponseCache:
    def __init__(self, ttl: float = _TTL_SECONDS, max_entries: int = _MAX_ENTRIES) -> None:
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[float, CachedResponse]] = OrderedDict()
        self._ttl = ttl
        self._max_entries = max_entries

    def get(self, key: str) -> CachedResponse | None:
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return payload

    def set(self, key: str, payload: CachedResponse) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + self._ttl, payload)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)


response_cache = ResponseCache()
