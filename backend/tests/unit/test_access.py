"""Rate-limiter gates: per-IP burst window, per-IP daily cap, global kill-switch."""

from app.core.config import settings
from app.security.access import InMemoryRateLimiter


def _tighten(monkeypatch, *, window_n, window_s, ip_daily, global_daily):
    monkeypatch.setattr(settings, "rate_limit_requests_per_window", window_n)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", window_s)
    monkeypatch.setattr(settings, "daily_request_limit", ip_daily)
    monkeypatch.setattr(settings, "global_daily_request_limit", global_daily)


def test_per_ip_window_blocks_burst(monkeypatch):
    _tighten(monkeypatch, window_n=3, window_s=300, ip_daily=1000, global_daily=1000)
    limiter = InMemoryRateLimiter()
    assert all(limiter.check("ip-a") is None for _ in range(3))
    retry = limiter.check("ip-a")
    assert isinstance(retry, int) and retry > 0
    # A different IP is unaffected by another IP's window.
    assert limiter.check("ip-b") is None


def test_per_ip_daily_cap_is_per_ip(monkeypatch):
    _tighten(monkeypatch, window_n=100, window_s=1, ip_daily=2, global_daily=1000)
    limiter = InMemoryRateLimiter()
    assert limiter.check("ip-a") is None
    assert limiter.check("ip-a") is None
    assert limiter.check("ip-a") is not None  # ip-a exhausted its daily cap
    assert limiter.check("ip-b") is None  # ip-b has its own daily budget


def test_global_cap_sheds_all_clients(monkeypatch):
    _tighten(monkeypatch, window_n=100, window_s=1, ip_daily=100, global_daily=2)
    limiter = InMemoryRateLimiter()
    assert limiter.check("ip-a") is None
    assert limiter.check("ip-b") is None  # global count now at 2
    # Even a brand-new IP is shed once the aggregate ceiling is hit.
    assert limiter.check("ip-c") is not None


def test_prune_drops_previous_day_counters(monkeypatch):
    _tighten(monkeypatch, window_n=100, window_s=1, ip_daily=100, global_daily=100)
    limiter = InMemoryRateLimiter()
    limiter._global_daily["1999-01-01"] = 50
    limiter._ip_daily["1999-01-01:ip-a"] = 50
    limiter._window_hits["1999-01-01:ip-a"].append(0.0)
    limiter.check("ip-a")  # triggers a prune for today
    assert "1999-01-01" not in limiter._global_daily
    assert "1999-01-01:ip-a" not in limiter._ip_daily
    assert "1999-01-01:ip-a" not in limiter._window_hits
