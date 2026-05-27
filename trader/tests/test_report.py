"""Verify write_report produces the expected files from a BacktestResult."""
import json
from datetime import date
from pathlib import Path
import pandas as pd
import pytest

from trader.engine import write_report
from trader.engine.runner import BacktestResult


def _sample_result() -> BacktestResult:
    return BacktestResult(
        strategy="pair_trading",
        params={"tickers": ("AMD", "NVDA"), "lookback": 30, "entry_z": 1.5},
        tickers=["AMD", "NVDA"],
        period=(date(2024, 1, 1), date(2024, 6, 30)),
        capital=100_000,
        metrics={
            "total_return": 0.05, "cagr": 0.10, "sharpe": 1.3,
            "sortino": 1.5, "max_drawdown": -0.05, "calmar": 2.0,
            "win_rate": 0.6, "profit_factor": 1.8, "total_trades": 12,
            "avg_trade_days": 5.0,
        },
        equity_curve=pd.Series(
            [0.001, -0.002, 0.005, 0.003, -0.001],
            index=pd.date_range("2024-01-02", periods=5),
        ),
        trade_log=[
            {"datetime": "2024-01-03T00:00:00", "side": "LONG", "ticker": "AMD",
             "size": 100, "price": 70.5, "reason": "entry z=-1.8"},
            {"datetime": "2024-01-10T00:00:00", "side": "EXIT", "ticker": "AMD",
             "size": 0, "price": 72.0, "reason": "mean reverted z=0.1"},
        ],
    )


def test_write_report_creates_all_artifacts(tmp_path):
    result = _sample_result()
    out = write_report(result, tmp_path / "run1")

    assert (out / "result.json").exists()
    assert (out / "trades.csv").exists()
    assert (out / "equity_curve.png").exists()
    assert (out / "drawdown.png").exists()

    payload = json.loads((out / "result.json").read_text())
    assert payload["strategy"] == "pair_trading"
    assert payload["tickers"] == ["AMD", "NVDA"]
    assert payload["capital"] == 100_000
    assert "run_at" in payload
    assert payload["metrics"]["sharpe"] == 1.3


def test_write_report_empty_equity_skips_plots(tmp_path):
    """No equity data -> JSON + CSV written, but no plots."""
    result = _sample_result()
    result.equity_curve = pd.Series(dtype=float)
    out = write_report(result, tmp_path / "run2")

    assert (out / "result.json").exists()
    assert (out / "trades.csv").exists()
    assert not (out / "equity_curve.png").exists()
    assert not (out / "drawdown.png").exists()


def test_write_report_handles_tuple_in_params(tmp_path):
    """Params can contain tuples (e.g. tickers); _jsonable converts safely."""
    result = _sample_result()
    out = write_report(result, tmp_path / "run3")
    payload = json.loads((out / "result.json").read_text())
    # tuple becomes list in JSON
    assert payload["params"]["tickers"] == ["AMD", "NVDA"]
