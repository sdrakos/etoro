#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only eToro real-price backtest of the GBT (and LSTM and fixed-rule) on the 18-asset basket.
Resolves tickers -> eToro instruments, fetches ~1000 daily candles, builds the 10 features, runs a
leak-free walk-forward, and charges REAL per-asset eToro spreads. NO orders are placed (candles +
search + rates only). Pure helpers are unit-tested; run() hits the live demo client."""
from __future__ import annotations
import sys, os
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "code"),
           os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"),
           os.path.join(HERE, "..", "..", "back")):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)
import crypto_features  # paper5/code

BASKET = ("BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD",
          "SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE")


def net_per_asset(W, fwd, spread_bps_vec, short_fin_annual=0.0):
    """W, fwd: (T,N) weights and next-bar returns. spread_bps_vec: (N,). Returns net stream (T,).
    Charges each asset's own spread on its own turnover (eToro spreads differ a lot per asset)."""
    W = np.asarray(W, float); fwd = np.asarray(fwd, float)
    gross = np.nansum(W * fwd, axis=1)
    turn = np.empty_like(W)
    turn[0] = np.abs(W[0])
    if len(W) > 1:
        turn[1:] = np.abs(W[1:] - W[:-1])
    cost = np.nansum(turn * (np.asarray(spread_bps_vec, float) / 1e4), axis=1)
    fin = (short_fin_annual / 1e4 / 252.0) * np.nansum(np.clip(-W, 0.0, None), axis=1)
    return gross - cost - fin


def panel_to_xy(close_2d, dates):
    """close_2d (T,N) + dates ['YYYY-MM-DD'] -> (X (N,T,10), fwd (N,T), dates_ms, vol (N,T causal),
    ppy, df). vol is annualised trailing-30 realized vol, shifted 1 bar (causal)."""
    idx = pd.to_datetime(dates)
    df = pd.DataFrame(np.asarray(close_2d, float), index=idx).ffill().dropna(how="all")
    X, fwd, dates_ms = crypto_features.build(df)
    days = (df.index[-1] - df.index[0]).days or 1
    ppy = len(df) / days * 365.0
    ret = df.pct_change()
    vol = (ret.rolling(30).std() * np.sqrt(ppy)).shift(1).to_numpy().T
    vol = np.nan_to_num(vol, nan=1.0)
    return X, fwd, dates_ms, vol, ppy, df
