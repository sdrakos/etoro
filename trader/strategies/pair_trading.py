"""Generic cointegration pair trading. Works on ANY 2 tickers.

Pattern:
    1. Rolling OLS hedge ratio β: y_t = α + β·x_t + ε_t
    2. Spread = y - β·x
    3. z-score on spread over lookback
    4. ADF test on spread; only trade when p < min_p_value
    5. Enter when |z| > entry_z, exit when |z| < exit_z, stop when |z| > stop_loss_z
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar

import backtrader as bt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

from trader.strategies.base import BaseStrategy


@dataclass
class PairParams:
    tickers: tuple[str, str] = ("AMD", "NVDA")
    lookback: int = 60
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_loss_z: float = 3.5
    capital_per_leg: float = 50_000
    min_p_value: float = 0.05


def compute_hedge_ratio(y: pd.Series, x: pd.Series) -> float:
    """OLS slope: y = α + β·x. Returns β."""
    X = sm.add_constant(x.to_numpy())
    model = sm.OLS(y.to_numpy(), X).fit()
    return float(model.params[1])


def compute_zscore(spread: pd.Series) -> float:
    """Standardize the last value of `spread` against its own mean/std."""
    mu = spread.mean()
    sigma = spread.std(ddof=0)
    if sigma == 0 or np.isnan(sigma):
        return 0.0
    return float((spread.iloc[-1] - mu) / sigma)


def cointegration_pvalue(spread: np.ndarray) -> float:
    """ADF p-value on the spread."""
    if len(spread) < 20:
        return 1.0
    try:
        result = adfuller(spread, autolag="AIC")
        return float(result[1])
    except (ValueError, np.linalg.LinAlgError):
        return 1.0


class PairTradingStrategy(BaseStrategy):
    """Generic 2-ticker cointegration pair trading."""
    name = "pair_trading"
    description = "Generic cointegration pair trading (any 2 tickers)"
    params_dataclass = PairParams

    params = (
        ("lookback", 60),
        ("entry_z", 2.0),
        ("exit_z", 0.5),
        ("stop_loss_z", 3.5),
        ("capital_per_leg", 50_000),
        ("min_p_value", 0.05),
    )

    def __init__(self):
        super().__init__()
        if len(self.datas) != 2:
            raise ValueError("pair_trading requires exactly 2 data feeds")
        self.y = self.datas[0]   # treated as y in OLS
        self.x = self.datas[1]   # treated as x in OLS
        self._position_state = "flat"  # flat | long_y_short_x | short_y_long_x

    @classmethod
    def required_tickers(cls, params: PairParams) -> list[str]:
        return list(params.tickers)

    def _recent_series(self, data, n: int) -> pd.Series:
        return pd.Series([data[-i] for i in range(n - 1, -1, -1)])

    def next(self):
        if len(self.y) < self.p.lookback or len(self.x) < self.p.lookback:
            return

        y_window = self._recent_series(self.y, self.p.lookback)
        x_window = self._recent_series(self.x, self.p.lookback)
        beta = compute_hedge_ratio(y_window, x_window)
        spread = y_window - beta * x_window
        z = compute_zscore(spread)
        p_value = cointegration_pvalue(spread.to_numpy())

        y_name = self.y._name
        x_name = self.x._name

        # Stop-loss check first (regardless of cointegration)
        if self._position_state != "flat" and abs(z) > self.p.stop_loss_z:
            self.close(data=self.y)
            self.close(data=self.x)
            self.log_trade("EXIT", y_name, 0, self.y[0], f"stop_loss z={z:.2f}")
            self.log_trade("EXIT", x_name, 0, self.x[0], f"stop_loss z={z:.2f}")
            self._position_state = "flat"
            return

        # Cointegration filter (no new entries if not cointegrated)
        if self._position_state == "flat" and p_value > self.p.min_p_value:
            return

        # Sizing: equal dollar
        size_y = self.p.capital_per_leg / self.y[0]
        size_x = self.p.capital_per_leg / self.x[0]

        if self._position_state == "flat":
            if z > self.p.entry_z:
                # Spread too high → short y, long x
                self.sell(data=self.y, size=size_y)
                self.buy(data=self.x, size=size_x * beta)
                self.log_trade("SHORT", y_name, size_y, self.y[0], f"entry z={z:.2f}")
                self.log_trade("LONG", x_name, size_x * beta, self.x[0], f"entry z={z:.2f}")
                self._position_state = "short_y_long_x"
            elif z < -self.p.entry_z:
                self.buy(data=self.y, size=size_y)
                self.sell(data=self.x, size=size_x * beta)
                self.log_trade("LONG", y_name, size_y, self.y[0], f"entry z={z:.2f}")
                self.log_trade("SHORT", x_name, size_x * beta, self.x[0], f"entry z={z:.2f}")
                self._position_state = "long_y_short_x"
        else:
            # In position — check exit
            if abs(z) < self.p.exit_z:
                self.close(data=self.y)
                self.close(data=self.x)
                self.log_trade("EXIT", y_name, 0, self.y[0], f"mean reverted z={z:.2f}")
                self.log_trade("EXIT", x_name, 0, self.x[0], f"mean reverted z={z:.2f}")
                self._position_state = "flat"
