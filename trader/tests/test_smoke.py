"""End-to-end: load fixture bars into cache → run pair_trading backtest → verify outputs."""
import csv
import json
from datetime import date
from pathlib import Path
import pytest

from trader.data.cache import Cache


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(ticker: str, cache: Cache):
    path = FIXTURE_DIR / f"{ticker.lower()}_2023.csv"
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append({
                "ticker": ticker,
                "timestamp": int(row["timestamp"]),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"]), "vwap": float(row["vwap"]),
            })
    cache.upsert(rows)


def test_full_backtest_pipeline(tmp_path, monkeypatch):
    """Pre-load cache with fixture bars; run pair_trading; verify report files exist."""
    db = tmp_path / "cache.db"
    monkeypatch.setattr("trader.data.loader.CACHE_DB", db)
    monkeypatch.setattr("trader.config.CACHE_DB", db)
    cache = Cache(db)
    _load_fixture("AMD", cache)
    _load_fixture("NVDA", cache)

    from trader.engine import run_backtest, write_report
    from trader.strategies.pair_trading import PairTradingStrategy

    params = {
        "tickers": ("AMD", "NVDA"),
        "lookback": 30,
        "entry_z": 1.5,
        "exit_z": 0.5,
        "stop_loss_z": 3.5,
        "capital_per_leg": 25_000,
        "min_p_value": 0.20,   # loose for short fixture sample
    }
    result = run_backtest(
        strategy_cls=PairTradingStrategy,
        params=params,
        tickers=["AMD", "NVDA"],
        start=date(2023, 1, 3),
        end=date(2023, 7, 1),
        capital=100_000,
    )

    out = write_report(result, tmp_path / "out")
    assert (out / "result.json").exists()
    payload = json.loads((out / "result.json").read_text())
    assert payload["strategy"] == "pair_trading"
    assert set(payload["metrics"].keys()) >= {
        "total_return", "sharpe", "sortino", "max_drawdown",
        "win_rate", "total_trades", "profit_factor",
    }
    assert (out / "trades.csv").exists()
