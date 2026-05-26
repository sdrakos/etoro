import backtrader as bt
import pytest

from trader.strategies.base import BaseStrategy, STRATEGY_REGISTRY


def test_subclass_auto_registers():
    """Defining a BaseStrategy subclass with a `name` attr registers it."""
    initial = set(STRATEGY_REGISTRY)

    class DummyStrategy(BaseStrategy):
        name = "dummy_test_strat"
        description = "Test strategy"

        from dataclasses import dataclass

        @dataclass
        class _P:
            window: int = 5

        params_dataclass = _P

    assert "dummy_test_strat" in STRATEGY_REGISTRY
    assert STRATEGY_REGISTRY["dummy_test_strat"] is DummyStrategy
    # Cleanup so test is rerunnable
    STRATEGY_REGISTRY.pop("dummy_test_strat", None)


def test_log_trade_appends_entry(monkeypatch):
    """Verify log_trade appends to internal list."""
    class _Strat(BaseStrategy):
        name = "log_trade_test"
        description = "x"
        params_dataclass = type("P", (), {})

    s = _Strat.__new__(_Strat)
    s._trade_log = []
    # backtrader's data feed datetime call — fake it
    s.datas = [type("D", (), {"datetime": type("DT", (), {"datetime": lambda self, offset: __import__("datetime").datetime(2024, 1, 1)})()})()]
    s.log_trade("LONG", "AAPL", 10, 100.5, "entry signal")
    assert len(s._trade_log) == 1
    assert s._trade_log[0]["ticker"] == "AAPL"
    STRATEGY_REGISTRY.pop("log_trade_test", None)
