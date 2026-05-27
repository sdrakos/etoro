"""Backtest orchestration: data feeds → Cerebro → analyzers → result."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Any
import pandas as pd
import backtrader as bt

from trader.data import load_bars
from trader.engine.analyzers import attach_default_analyzers, extract_metrics, extract_equity_curve


@dataclass
class BacktestResult:
    strategy: str
    params: dict
    tickers: list[str]
    period: tuple[date, date]
    capital: float
    metrics: dict[str, Any]
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    trade_log: list[dict] = field(default_factory=list)


def _bars_to_feed(df: pd.DataFrame, name: str) -> bt.feeds.PandasData:
    """Convert our DataFrame to a backtrader PandasData feed."""
    bt_df = df.rename(columns={"open": "open", "high": "high", "low": "low",
                                "close": "close", "volume": "volume"}).copy()
    bt_df.index = bt_df.index.tz_convert(None) if bt_df.index.tz else bt_df.index
    return bt.feeds.PandasData(dataname=bt_df, name=name,
                                open="open", high="high", low="low",
                                close="close", volume="volume", openinterest=None)


def run_backtest(
    strategy_cls,
    params: dict,
    tickers: list[str],
    start: date,
    end: date,
    capital: float = 100_000,
    commission: float = 0.00005,   # 0.5 bps
    slippage_perc: float = 0.0001, # 1 bp
    timespan: str = "day",
) -> BacktestResult:
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=commission)
    cerebro.broker.set_slippage_perc(perc=slippage_perc)

    for ticker in tickers:
        df = load_bars(ticker, start, end, timespan=timespan)
        if df.empty:
            raise RuntimeError(f"No bars for {ticker} in [{start}, {end}]")
        cerebro.adddata(_bars_to_feed(df, ticker))

    valid_param_names = set(strategy_cls.params._getkeys())
    bt_params = {k: v for k, v in params.items() if k in valid_param_names}
    cerebro.addstrategy(strategy_cls, **bt_params)
    attach_default_analyzers(cerebro)

    results = cerebro.run()
    strat = results[0]

    return BacktestResult(
        strategy=strategy_cls.name,
        params=params,
        tickers=tickers,
        period=(start, end),
        capital=capital,
        metrics=extract_metrics(strat),
        equity_curve=extract_equity_curve(strat),
        trade_log=strat._trade_log,
    )
