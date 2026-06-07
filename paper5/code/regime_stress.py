#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper5 Phase-2: regime-stress + durability. The banded configs had near-zero turnover —
is the edge REAL across regimes, or just "slow long-only in a bull"? Year-by-year net IR
(incl. the 2022 bear) is the test. Deep daily, ETF + crypto, net of a realistic 10 bps.
Reuses paper4 cost/metrics. Data: Yahoo daily (yfinance)."""
import sys, os
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import yfinance as yf

ETF = ["SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD"]
BPS = 10.0
TARGET_VOL = 0.15


def fetch_daily(tickers, period="13y"):
    df = yf.download(tickers, period=period, interval="1d", auto_adjust=True, progress=False, group_by="ticker")
    cols = {}
    for t in tickers:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 300: cols[t] = s
        except Exception: pass
    return pd.DataFrame(cols).sort_index()


def apply_band(pos, band):
    T, N = pos.shape; held = np.zeros_like(pos); cur = np.zeros(N)
    for t in range(T):
        upd = np.abs(pos[t] - cur) > band
        cur = np.where(upd, pos[t], cur); held[t] = cur
    return held


def evaluate(close, label, mom_lb, vol_lb=30, smooth=1, band=0.0):
    close = close.ffill().dropna(how="all")
    days = (close.index[-1] - close.index[0]).days or 1
    ppy = len(close) / days * 365.0
    ret = close.pct_change()
    vol = ret.rolling(vol_lb).std() * np.sqrt(ppy)
    sig = np.sign(close.pct_change(mom_lb))
    pos = (sig * (TARGET_VOL / vol.shift(1))).clip(-2, 2).fillna(0.0)
    if smooth > 1: pos = pos.ewm(span=smooth, min_periods=1).mean()
    P = apply_band(pos.values, band) if band > 0 else pos.values
    w = P / close.shape[1]
    fwd = ret.shift(-1).values
    m = np.isfinite(fwd).all(axis=1)
    W, F, idx = w[m], fwd[m], close.index[m]
    net = costs.net_returns(W, F, BPS, 0)
    gross = costs.net_returns(W, F, 0, 0)
    fin = np.isfinite(net)
    net, gross, idx = net[fin], gross[fin], idx[fin]
    eq = np.cumprod(1 + net)
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    s = pd.Series(net, index=idx)
    dur = {int(y): round(metrics.ann_ir(g.values, ppy), 2) for y, g in s.groupby(s.index.year) if len(g) > 20}
    print(f"\n{label}: grossIR {metrics.ann_ir(gross,ppy):+.2f} | netIR@{int(BPS)}bps {metrics.ann_ir(net,ppy):+.2f} "
          f"| maxDD {mdd:.0%} | NW-t {metrics.newey_west_t(net):+.2f}")
    yrs = " ".join(f"{y}:{ir:+.1f}" for y, ir in dur.items())
    print("  net IR by year: " + yrs)
    return dur


if __name__ == "__main__":
    print("=== ETF daily (deep) ===")
    e = fetch_daily(ETF); print(f"  {e.shape[1]} assets, {len(e)} bars, {e.index[0].date()}..{e.index[-1].date()}")
    evaluate(e, "ETF baseline (mom60)", 60)
    evaluate(e, "ETF banded (mom120,band0.3)", 120, smooth=5, band=0.3)
    print("\n=== CRYPTO daily (deep) ===")
    c = fetch_daily(CRYPTO); print(f"  {c.shape[1]} assets, {len(c)} bars, {c.index[0].date()}..{c.index[-1].date()}")
    evaluate(c, "CRYPTO baseline (mom60)", 60)
    evaluate(c, "CRYPTO banded (mom120,band0.3)", 120, smooth=5, band=0.3)
    print("\nKey test: does net IR stay >0 in 2022 (bear)? If it collapses, it was a bull artifact.")
