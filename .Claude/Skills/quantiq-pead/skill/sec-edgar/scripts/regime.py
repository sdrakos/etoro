#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regime.py — the risk "brake": scale exposure by the market's volatility state.

Volatility is far more predictable than returns (vol clustering). This layer does NOT
predict direction — it sizes the existing book down when the market gets stormy and up
when it's calm (volatility targeting; Moreira-Muir). It is the transferable version of
Jane Street's "regime-y data" handling and your DER state-dependent theta.

All multipliers use only PAST information (shifted), so there is no look-ahead.
"""

import numpy as np
import pandas as pd


def realized_vol(market_ret, lookback=20):
    """Annualized rolling realized volatility of a daily market return series."""
    return market_ret.rolling(lookback).std() * np.sqrt(252)


def vol_target_multiplier(market_ret, target_vol=0.10, lookback=20, cap=2.0):
    """Exposure multiplier = target_vol / recent_realized_vol, capped, shifted by 1 day."""
    rv = realized_vol(market_ret, lookback)
    mult = (target_vol / rv.replace(0, np.nan)).clip(0, cap)
    return mult.shift(1).fillna(0.0)          # use yesterday's vol -> no look-ahead


def regime_throttle(market_ret, lookback=20, hi_q=0.80, hi_mult=0.5, lo_mult=1.0):
    """Discrete brake: when realized vol is in its top quantile (expanding), cut to hi_mult."""
    rv = realized_vol(market_ret, lookback)
    thr = rv.expanding(min_periods=60).quantile(hi_q)
    m = pd.Series(np.where(rv > thr, hi_mult, lo_mult), index=market_ret.index)
    return m.shift(1).fillna(lo_mult)


def apply_regime(port_ret, market_ret, mode="vol_target", **kw):
    """Scale a portfolio return series by the chosen regime multiplier.
    Returns (scaled_returns, multiplier_series)."""
    if mode == "throttle":
        mult = regime_throttle(market_ret, **kw)
    else:
        mult = vol_target_multiplier(market_ret, **kw)
    mult = mult.reindex(port_ret.index).fillna(0.0)
    return port_ret * mult, mult


if __name__ == "__main__":
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2015-01-01", periods=1500)
    vol = 0.01 + 0.03*(np.sin(np.arange(len(days))/120)**2)     # vol clustering
    mkt = pd.Series(rng.normal(0, vol), index=days)
    port = pd.Series(rng.normal(0.0003, 0.01, len(days)), index=days) - 0.5*mkt
    scaled, mult = apply_regime(port, mkt, mode="vol_target", target_vol=0.10)
    ir = lambda x: np.sqrt(252)*x.mean()/(x.std()+1e-12)
    print(f"raw IR {ir(port):.2f} | regime-scaled IR {ir(scaled):.2f} | "
          f"mult range {mult.min():.2f}-{mult.max():.2f}")
