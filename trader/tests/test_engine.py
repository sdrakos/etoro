"""Engine integration test: run_backtest works with a real strategy."""
import datetime as dt
from datetime import date

import numpy as np
import pandas as pd
import pytest

from trader.data.cache import Cache
from trader.strategies.pair_trading import PairTradingStrategy


def _make_synthetic_bars(ticker: str, n_days: int, base: float, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    bars = []
    price = base
    d = date(2024, 1, 1)
    for _ in range(n_days):
        # Skip weekends
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        ts = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
        o = price
        h = o * (1 + abs(rng.normal(0, 0.01)))
        l = o * (1 - abs(rng.normal(0, 0.01)))
        c = o + rng.normal(0, o * 0.012)
        bars.append({
            "ticker": ticker, "timestamp": ts,
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(c, 2),
            "volume": 1_000_000, "vwap": round((o + h + l + c) / 4, 2),
        })
        price = c
        d += dt.timedelta(days=1)
    return bars


def test_run_backtest_executes_pair_trading(temp_db, monkeypatch):
    """End-to-end: run_backtest must not crash on the param filter line."""
    from trader.engine import run_backtest

    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)
    cache = Cache(temp_db)

    # Two correlated synthetic series so cointegration can fire
    cache.upsert(_make_synthetic_bars("AMD", 120, 70.0, seed=1))
    cache.upsert(_make_synthetic_bars("NVDA", 120, 140.0, seed=2))

    params = {
        "tickers": ("AMD", "NVDA"),
        "lookback": 30,
        "entry_z": 1.5,
        "exit_z": 0.5,
        "stop_loss_z": 4.0,
        "capital_per_leg": 25_000,
        "min_p_value": 0.50,  # loose for synthetic
    }
    result = run_backtest(
        strategy_cls=PairTradingStrategy,
        params=params,
        tickers=["AMD", "NVDA"],
        start=date(2024, 1, 1),
        end=date(2024, 7, 1),
        capital=100_000,
    )

    assert result.strategy == "pair_trading"
    assert result.tickers == ["AMD", "NVDA"]
    assert set(result.metrics.keys()) >= {
        "total_return", "sharpe", "sortino", "max_drawdown",
        "win_rate", "total_trades",
    }
    # No assertion on trade count — synthetic data may not trigger any —
    # the important check is that run_backtest completed.
