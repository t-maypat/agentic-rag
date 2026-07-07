"""Public-demo access control: sliding-window rate limiting + hCaptcha.

Ported from the original ``services/public_access.py`` with two changes per the
revamp plan: client IP is derived only from the last ``TRUSTED_PROXY`` hops of
``X-Forwarded-For`` (no blind trust of the spoofable leftmost value), and the
cookie/session-signing machinery is removed (thread ids are unguessable UUIDs
minted server-side; no PII in cookies).
"""

import hashlib
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Final

import httpx
from fastapi import HTTPException, Request, status

from app.core.config import settings

HCAPTCHA_VERIFY_URL: Final[str] = "https://api.hcaptcha.com/siteverify"


def client_ip(request: Request) -> str:
    """Resolve the client IP, trusting only ``TRUSTED_PROXY`` proxy hops.

    With N trusted proxies in front of the app, the rightmost N entries of
    ``X-Forwarded-For`` were appended by trusted infrastructure; the real client
    is the Nth entry from the right. Direct connections use the peer address.
    """
    hops = settings.trusted_proxy
    if hops > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [part.strip() for part in forwarded.split(",") if part.strip()]
            if len(parts) >= hops:
                return parts[-hops]
            if parts:
                return parts[0]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _hash_ip(ip_address: str) -> str:
    return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()[:16]


class InMemoryRateLimiter:
    """Single-instance limiter (resets on restart) with three independent gates:

    1. per-IP short burst window (``rate_limit_requests_per_window`` / window),
    2. per-IP daily cap (``daily_request_limit``),
    3. an aggregate daily kill-switch across all clients
       (``global_daily_request_limit``) that bounds total API spend even under
       distributed, rotating-IP abuse.

    Documented limitation (§5.4): per-process, in-memory. Behind more than one
    instance, or against attackers rotating IPs faster than the window, only the
    global gate meaningfully caps spend — an edge WAF/CDN is the real DDoS defence.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._window_hits: dict[str, deque[float]] = defaultdict(deque)
        self._ip_daily: dict[str, int] = defaultdict(int)  # key: "YYYY-MM-DD:iphash"
        self._global_daily: dict[str, int] = defaultdict(int)  # key: "YYYY-MM-DD"

    def _prune_locked(self, day_key: str) -> None:
        """Drop counters from previous days so memory stays bounded across days."""
        prefix = f"{day_key}:"
        for store in (self._window_hits, self._ip_daily):
            for stale in [k for k in store if not k.startswith(prefix)]:
                del store[stale]
        for stale in [d for d in self._global_daily if d != day_key]:
            del self._global_daily[stale]

    def check(self, key: str) -> int | None:
        """Return None if allowed, else a Retry-After hint in seconds."""
        now = time.time()
        cutoff = now - settings.rate_limit_window_seconds
        day_key = datetime.now(UTC).strftime("%Y-%m-%d")
        scoped_key = f"{day_key}:{key}"

        with self._lock:
            self._prune_locked(day_key)

            # Aggregate spend ceiling first: once tripped, everyone is shed.
            if self._global_daily[day_key] >= settings.global_daily_request_limit:
                return settings.rate_limit_window_seconds

            bucket = self._window_hits[scoped_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= settings.rate_limit_requests_per_window:
                return max(1, int(settings.rate_limit_window_seconds - (now - bucket[0])))

            if self._ip_daily[scoped_key] >= settings.daily_request_limit:
                return settings.rate_limit_window_seconds

            bucket.append(now)
            self._ip_daily[scoped_key] += 1
            self._global_daily[day_key] += 1
            return None


class PublicAccess:
    def __init__(self) -> None:
        self._rate_limiter = InMemoryRateLimiter()

    async def _verify_hcaptcha(self, token: str, remote_ip: str) -> None:
        if not settings.hcaptcha_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="hCaptcha protection is enabled but not configured on the server.",
            )
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    HCAPTCHA_VERIFY_URL,
                    data={
                        "secret": settings.hcaptcha_secret_key,
                        "response": token,
                        "remoteip": remote_ip,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="hCaptcha verification is temporarily unavailable.",
                ) from exc
        if not response.json().get("success"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="hCaptcha verification failed. Please try again.",
            )

    def check_rate_limit(self, request: Request) -> None:
        remote_ip = client_ip(request)
        retry_after = self._rate_limiter.check(_hash_ip(remote_ip))
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limited. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    async def verify_captcha(self, request: Request, token: str | None) -> None:
        if not settings.require_hcaptcha:
            return
        token = request.headers.get("x-hcaptcha-token") or token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="hCaptcha verification is required.",
            )
        await self._verify_hcaptcha(token, client_ip(request))

    def validate_question(self, question: str) -> None:
        if len(question.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question is required."
            )
        if len(question) > settings.question_max_chars:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Question exceeds the {settings.question_max_chars}-character limit.",
            )

    async def enforce_research_access(
        self,
        request: Request,
        question: str,
        captcha_token: str | None,
    ) -> None:
        self.validate_question(question)
        self.check_rate_limit(request)
        await self.verify_captcha(request, captcha_token)


public_access = PublicAccess()
