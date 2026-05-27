"""Write a BacktestResult to an output folder (JSON + CSV + PNGs)."""
from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # no GUI
import matplotlib.pyplot as plt

from trader.engine.runner import BacktestResult


def write_report(result: BacktestResult, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. result.json
    payload = {
        "strategy": result.strategy,
        "params": _jsonable(result.params),
        "tickers": result.tickers,
        "period": [result.period[0].isoformat(), result.period[1].isoformat()],
        "capital": result.capital,
        "metrics": result.metrics,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "result.json").write_text(json.dumps(payload, indent=2, default=str))

    # 2. trades.csv
    trades_df = pd.DataFrame(result.trade_log)
    trades_df.to_csv(out / "trades.csv", index=False)

    # 3. equity_curve.png
    if not result.equity_curve.empty:
        eq = (1 + result.equity_curve).cumprod() * result.capital
        plt.figure(figsize=(10, 5))
        eq.plot(title=f"Equity Curve - {result.strategy} {result.tickers}")
        plt.ylabel("Portfolio Value")
        plt.tight_layout()
        plt.savefig(out / "equity_curve.png", dpi=120)
        plt.close()

        # 4. drawdown.png
        roll_max = eq.cummax()
        dd = (eq - roll_max) / roll_max
        plt.figure(figsize=(10, 4))
        dd.plot(title="Drawdown", color="red")
        plt.fill_between(dd.index, dd.values, 0, color="red", alpha=0.3)
        plt.ylabel("Drawdown")
        plt.tight_layout()
        plt.savefig(out / "drawdown.png", dpi=120)
        plt.close()

    return out


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj
