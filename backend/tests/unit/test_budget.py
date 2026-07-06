import time

import pytest

from app.agent import budget
from app.agent.errors import BudgetExceeded
from app.agent.state import BudgetLedger


def test_record_llm_accumulates():
    ledger = budget.new_ledger()
    budget.record_llm(ledger, 100, 40)
    budget.record_llm(ledger, 50, 10)
    assert ledger.llm_calls == 2
    assert ledger.input_tokens == 150
    assert ledger.output_tokens == 50


def test_check_passes_within_limits():
    ledger = budget.new_ledger()
    budget.record_llm(ledger, 10, 5)
    budget.check(ledger, "quick")  # no raise


def test_check_raises_on_llm_calls():
    ledger = budget.new_ledger()
    ledger.llm_calls = budget.MAX_LLM_CALLS
    with pytest.raises(BudgetExceeded):
        budget.check(ledger, "quick")


def test_check_raises_on_tokens():
    ledger = budget.new_ledger()
    ledger.input_tokens = budget.MAX_TOTAL_TOKENS
    with pytest.raises(BudgetExceeded):
        budget.check(ledger, "deep")


def test_check_raises_on_wall_clock():
    ledger = BudgetLedger(started_at=time.monotonic() - budget.MAX_WALL_SECONDS_QUICK - 1)
    with pytest.raises(BudgetExceeded):
        budget.check(ledger, "quick")


def test_est_cost_is_positive_and_rounded():
    ledger = budget.new_ledger()
    budget.record_llm(ledger, 1_000_000, 1_000_000)
    cost = budget.est_cost_usd(ledger, "gemini-2.5-flash", "gemini-2.5-flash-lite")
    assert cost > 0
    assert round(cost, 6) == cost
