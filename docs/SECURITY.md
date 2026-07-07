# Security — Loupe

Loupe runs as a public demo on free tiers, so the threat model centers on **abuse
that burns API budget or degrades availability**, plus **prompt injection** from
web evidence. This document is the source of truth for what is mitigated, what is
accepted, and what is still planned.

## Threat model

| Asset | Threat | Mitigation (in place) | Residual risk |
|---|---|---|---|
| Gemini/Tavily API budget | Automated/bot request floods burning tokens & quota | Per-IP burst window (8/5min) + per-IP daily cap (200) + **global daily kill-switch** (`GLOBAL_DAILY_REQUEST_LIMIT`, default 2000) + per-request **budget governor** (≤10 LLM calls, ≤80k tokens, ≤90s) + exact-match response cache | Distributed (rotating-IP) abuse still consumes up to the global cap/day; free-tier vendor quotas (429 + backoff) are the backstop. Edge WAF not yet in front. |
| Availability | L7 flood / many concurrent SSE connections exhausting the single 512 MB instance | Access checks run **before** streaming starts (unauthorized floods get 429/403 without holding an SSE connection); `ping`/`X-Accel-Buffering` keep legit streams alive | No per-instance concurrency cap; no edge/CDN rate limiting. A determined flood can still saturate one instance. |
| API budget (write path) | Hitting the expensive tail of the graph directly | `POST /api/research/{id}/approve` now **rate-limited**; resuming requires a valid pending interrupt on an unguessable UUID thread | Not captcha'd (by design, §10.1) — rate limit is the only gate. |
| Server files | LFI via ingest | HTTP ingest endpoint **deleted**; ingestion is CLI-only (`scripts/ingest.py`, reads `data/corpus/` only) | None. |
| Model / answer integrity | Prompt injection inside fetched web pages | Sanitizer strips HTML→text, truncates, wraps in `<web_evidence>` tags; prompts mark web content untrusted; regex flagger demotes injection strings to `trust:"low"` (excluded from synthesis) | Novel injection phrasings the flagger misses; capped by "web content is data, not instructions" prompt framing. |
| Bot signups / scripted abuse | Non-human traffic | hCaptcha verified **server-side** on `/api/research` when `REQUIRE_HCAPTCHA=1` | Client can call the API directly, so captcha is a friction/cost gate, not authn. |
| Secrets | Key leakage | Keys only in server env; never sent to client; `/health` exposes booleans only; generic error messages, details to logs | Operator misconfig (e.g. committing `.env`). |
| Cross-origin abuse | Hostile sites calling the API with credentials | CORS locked to `CORS_ORIGINS` (comma-separated now parses correctly); no cookies/credentials used by the client | Misconfigured `CORS_ORIGINS=*` in prod would open it — see checklist. |
| Client IP spoofing (defeats rate limits) | Forged `X-Forwarded-For` | IP derived only from the last `TRUSTED_PROXY` hops | If `TRUSTED_PROXY` is set too high, headers become spoofable — set to the real hop count (Render = 1). |

## What changed in the hardening pass

- **Global daily kill-switch** (`global_daily_request_limit`, default 2000) added to the
  limiter as an aggregate ceiling across *all* clients — the primary defense against
  distributed API-budget burn. The previous "daily cap" was effectively global by
  accident; the daily cap is now correctly **per-IP**, with the global cap separate.
- **`/approve` is rate-limited** — it triggers retrieve/web/synthesize/verify.
- **`CORS_ORIGINS` comma-separated parsing fixed** — previously a comma-separated
  value (as documented) raised `SettingsError` and crashed the app at startup.
- Limiter now **prunes previous-day counters** so memory stays bounded.

## hCaptcha placement — assessment

- **Where:** rendered below the composer whenever `VITE_HCAPTCHA_SITE_KEY` is set. Fine.
- **When:** a fresh solve is required on *every* query. This is **correct**, not
  over-zealous: hCaptcha tokens are single-use with a ~2-minute TTL, so a token
  cannot be reused across requests. Re-solving per query is the secure behavior.
- **Coupling footgun:** the frontend shows/requires the widget based on the *site
  key*, while the backend enforces based on `REQUIRE_HCAPTCHA`. If these drift
  (backend on, site key unset), users get an unresolvable 403. Keep them set together.
- **Optional UX improvement (not required for security):** switch to hCaptcha
  **invisible** mode (`execute()` on submit) so the challenge only surfaces when the
  session looks suspicious — same protection, less friction for multi-turn.

## Remaining hardening plan (prioritized)

1. **Edge WAF / CDN in front (highest impact).** Put Cloudflare (free) ahead of the
   Render backend for L3/L4 DDoS absorption and edge rate limiting by IP/ASN — far
   stronger than per-process in-memory limits. This is the single biggest gap for a
   truly public deployment.
2. **Global Tavily fetch cap.** A per-day aggregate web-fetch ceiling (Tavily free
   tier = 1000/mo) so deep-mode abuse can't exhaust the monthly quota; today only the
   per-request cap (3) exists.
3. **SSE concurrency cap.** Bound concurrent in-flight research streams per instance
   to protect the threadpool/memory under a slow-loris-style SSE flood.
4. **Thread store growth bound.** `threads.db` grows one row-set per request on the
   ephemeral disk; add a TTL/size cap or periodic prune (disk loss on redeploy is the
   current safety valve).
5. **Shared limiter store when scaling past one instance.** The in-memory limiter is
   per-process; a second instance doubles effective limits. Move to Redis (or rely on
   the edge WAF) before horizontal scaling.

## Production configuration checklist

- [ ] `APP_ENV=production`
- [ ] `REQUIRE_HCAPTCHA=1` **and** frontend `VITE_HCAPTCHA_SITE_KEY` set (both, together)
- [ ] `HCAPTCHA_SECRET_KEY` set server-side
- [ ] `REQUIRE_DEEP_APPROVAL=1`
- [ ] `CORS_ORIGINS` = exact Vercel domain(s), **never** `*`
- [ ] `TRUSTED_PROXY=1` (Render) — not higher
- [ ] Tune `GLOBAL_DAILY_REQUEST_LIMIT` / `DAILY_REQUEST_LIMIT` for expected traffic
- [ ] `.env` not committed; keys rotated if ever exposed
- [ ] (Recommended) Cloudflare in front with an edge rate-limit rule
