import pytest

from argus.guards import BudgetExceeded, BudgetGuard, CircuitBreaker, LoopDetector


def test_budget_steps():
    g = BudgetGuard(max_steps=2)
    g.tick()
    g.tick()
    with pytest.raises(BudgetExceeded):
        g.check()


def test_budget_tokens():
    g = BudgetGuard(max_tokens=100)
    g.tick(tokens=150)
    with pytest.raises(BudgetExceeded):
        g.check()


def test_loop_detector_triggers():
    d = LoopDetector(limit=2)
    assert not d.observe("search", {"q": "x"})
    assert d.observe("search", {"q": "x"})


def test_loop_detector_distinguishes_args():
    d = LoopDetector(limit=2)
    d.observe("search", {"q": "x"})
    assert not d.observe("search", {"q": "y"})


def test_breaker_opens_and_resets(monkeypatch):
    b = CircuitBreaker(threshold=2, cooldown_s=10)
    b.record("fetch", False)
    assert not b.is_open("fetch")
    b.record("fetch", False)
    assert b.is_open("fetch")
    b.opened_at["fetch"] -= 11
    assert not b.is_open("fetch")


def test_breaker_success_resets_failures():
    b = CircuitBreaker(threshold=2)
    b.record("x", False)
    b.record("x", True)
    b.record("x", False)
    assert not b.is_open("x")
