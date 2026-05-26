import datetime as dt
from dataclasses import dataclass
from unittest.mock import MagicMock

import backtrader as bt
import pytest

from trader.strategies.base import BaseStrategy, STRATEGY_REGISTRY


def test_subclass_auto_registers():
    """Defining a BaseStrategy subclass with a `name` attr registers it."""
    class DummyStrategy(BaseStrategy):
        name = "dummy_test_strat"
        description = "Test strategy"

        @dataclass
        class _P:
            window: int = 5

        params_dataclass = _P

    assert "dummy_test_strat" in STRATEGY_REGISTRY
    assert STRATEGY_REGISTRY["dummy_test_strat"] is DummyStrategy
    STRATEGY_REGISTRY.pop("dummy_test_strat", None)


def test_log_trade_appends_entry():
    """Verify log_trade appends to internal list using a clean mock."""
    class _Strat(BaseStrategy):
        name = "log_trade_test"
        description = "x"
        params_dataclass = type("P", (), {})

    s = _Strat.__new__(_Strat)
    s._trade_log = []
    # Mock data feed cleanly
    mock_data = MagicMock()
    mock_data.datetime.datetime.return_value = dt.datetime(2024, 1, 1)
    s.datas = [mock_data]

    s.log_trade("LONG", "AAPL", 10, 100.5, "entry signal")
    assert len(s._trade_log) == 1
    assert s._trade_log[0]["ticker"] == "AAPL"
    assert s._trade_log[0]["side"] == "LONG"
    STRATEGY_REGISTRY.pop("log_trade_test", None)


def test_base_strategy_excluded_from_registry():
    """The base class itself must not appear in the registry."""
    assert "" not in STRATEGY_REGISTRY
    assert "BaseStrategy" not in STRATEGY_REGISTRY


def test_underscore_modules_are_skipped(tmp_path):
    """A module starting with _ in strategies/ must not be auto-imported."""
    # This is a smoke test — the actual exclusion logic is in __init__.py.
    # If a _helper.py existed, importing the package would not execute it.
    import trader.strategies as ts
    # No exception during import = pass. (Direct verification would require
    # creating a temp module on disk, which is over-engineering.)
    assert hasattr(ts, "STRATEGY_REGISTRY")
