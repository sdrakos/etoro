"""Metric extractors that translate backtrader Analyzers to flat dicts."""
from __future__ import annotations
from typing import Any

import backtrader as bt


def attach_default_analyzers(cerebro: bt.Cerebro) -> None:
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.04, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.SortinoRatio, _name="sortino", riskfreerate=0.04)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days)


def extract_metrics(strat: bt.Strategy) -> dict[str, Any]:
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio")
    sortino = strat.analyzers.sortino.get_analysis().get("sortinoratio")
    dd = strat.analyzers.dd.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    total_trades = trades.get("total", {}).get("closed", 0)
    won = trades.get("won", {}).get("total", 0)
    lost = trades.get("lost", {}).get("total", 0)
    pnl_won = trades.get("won", {}).get("pnl", {}).get("total", 0.0)
    pnl_lost = abs(trades.get("lost", {}).get("pnl", {}).get("total", 0.0))

    win_rate = (won / total_trades) if total_trades else 0.0
    profit_factor = (pnl_won / pnl_lost) if pnl_lost else float("inf") if pnl_won else 0.0

    max_dd = dd.get("max", {}).get("drawdown", 0.0) / 100.0  # percent → fraction
    cagr = returns.get("rnorm", 0.0)
    total_return = returns.get("rtot", 0.0)
    calmar = (cagr / abs(max_dd)) if max_dd else 0.0

    avg_len = trades.get("len", {}).get("average", 0)

    return {
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "sharpe": round(sharpe, 4) if sharpe else None,
        "sortino": round(sortino, 4) if sortino else None,
        "max_drawdown": -round(abs(max_dd), 6),
        "calmar": round(calmar, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "total_trades": int(total_trades),
        "avg_trade_days": float(avg_len),
    }


def extract_equity_curve(strat: bt.Strategy):
    """Return pd.Series of daily returns from TimeReturn analyzer."""
    import pandas as pd
    timereturn = strat.analyzers.timereturn.get_analysis()
    if not timereturn:
        return pd.Series(dtype=float)
    return pd.Series(timereturn).sort_index()
