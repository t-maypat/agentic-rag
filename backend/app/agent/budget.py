"""Budget governor: per-request limits, cost pricing, and ledger accounting.

``check()`` is called by the grade router (the natural gate of the retrieve →
rewrite loop) and raises :class:`BudgetExceeded`, which routes the graph to
``finalize`` with ``outcome="budget_exceeded"``. Token counts are recorded by the
``LLMClient`` adapter via :func:`record_llm`.
"""

import time

from app.agent.errors import BudgetExceeded
from app.agent.state import BudgetLedger

# Hard limits (REVAMP_PLAN §3.1 / §17.8).
MAX_LLM_CALLS = 10
MAX_TOTAL_TOKENS = 80_000
MAX_WEB_FETCHES = 3
MAX_WALL_SECONDS_DEEP = 90.0
MAX_WALL_SECONDS_QUICK = 25.0

# Max rewrite loops (retrieve runs at most MAX_REWRITES + 1 times).
MAX_REWRITES = 2

# Gemini paid-tier list prices (USD per 1M tokens). Used for the est. cost ledger
# even on the free tier; the UI labels it "est. at list price".
PRICES_ASOF = "2026-07"
_PRICES: dict[str, tuple[float, float]] = {
    # model: (input_per_1m, output_per_1m)
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}
_DEFAULT_PRICE = (0.30, 2.50)


def new_ledger() -> BudgetLedger:
    return BudgetLedger(started_at=time.monotonic())


def record_llm(ledger: BudgetLedger, input_tokens: int, output_tokens: int) -> None:
    ledger.llm_calls += 1
    ledger.input_tokens += max(0, input_tokens)
    ledger.output_tokens += max(0, output_tokens)


def record_web_fetch(ledger: BudgetLedger) -> None:
    ledger.web_fetches += 1


def _wall_limit(mode: str) -> float:
    return MAX_WALL_SECONDS_QUICK if mode == "quick" else MAX_WALL_SECONDS_DEEP


def wall_ms(ledger: BudgetLedger) -> int:
    if not ledger.started_at:
        return 0
    return int((time.monotonic() - ledger.started_at) * 1000)


def check(ledger: BudgetLedger, mode: str) -> None:
    """Raise :class:`BudgetExceeded` if any hard limit is exceeded."""
    if ledger.llm_calls >= MAX_LLM_CALLS:
        raise BudgetExceeded(f"llm_calls={ledger.llm_calls} >= {MAX_LLM_CALLS}")
    if ledger.input_tokens + ledger.output_tokens >= MAX_TOTAL_TOKENS:
        raise BudgetExceeded("token budget exhausted")
    if ledger.web_fetches > MAX_WEB_FETCHES:
        raise BudgetExceeded(f"web_fetches={ledger.web_fetches} > {MAX_WEB_FETCHES}")
    if ledger.started_at and (time.monotonic() - ledger.started_at) >= _wall_limit(mode):
        raise BudgetExceeded("wall-clock budget exhausted")


def est_cost_usd(ledger: BudgetLedger, model_synth: str, model_control: str) -> float:
    """Rough cost estimate. Control-flow calls dominate in count; synthesis in
    output tokens. We attribute input tokens at the control price and output at
    the synth price — a deliberate approximation documented as such in the UI."""
    in_price = _PRICES.get(model_control, _DEFAULT_PRICE)[0]
    out_price = _PRICES.get(model_synth, _DEFAULT_PRICE)[1]
    cost = (ledger.input_tokens / 1_000_000) * in_price
    cost += (ledger.output_tokens / 1_000_000) * out_price
    return round(cost, 6)
