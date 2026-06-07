#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper5 Phase-2 probe v2: can we lift break-even cost above reality via the two legitimate
levers — (a) TURNOVER REDUCTION (slower signal + EWMA smoothing + no-trade band) and
(b) a CRYPTO 24/7 basket (stronger trends)? Same leak-free, cost-swept TSMOM as v1.
Data: Yahoo intraday (yfinance). Reuses paper4 cost/metrics."""
import sys, os
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import yfinance as yf

ETF = ["SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD"]
BPS_GRID = [0, 1, 2, 5, 10, 15, 20, 30, 50, 80]
TARGET_VOL = 0.15


def fetch_1h(tickers):
    df = yf.download(tickers, period="730d", interval="1h", auto_adjust=True, progress=False, group_by="ticker")
    cols = {}
    for t in tickers:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 800: cols[t] = s
        except Exception: pass
    return pd.DataFrame(cols).sort_index()


def fetch_daily(tickers, period="12y"):
    df = yf.download(tickers, period=period, interval="1d", auto_adjust=True, progress=False, group_by="ticker")
    cols = {}
    for t in tickers:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 400: cols[t] = s
        except Exception: pass
    return pd.DataFrame(cols).sort_index()


def apply_band(pos, band):
    """No-trade band: per asset, only move to a new target if it differs from the held
    position by more than `band`; else hold. Kills churn turnover. Sequential (causal)."""
    T, N = pos.shape
    held = np.zeros_like(pos); cur = np.zeros(N)
    for t in range(T):
        upd = np.abs(pos[t] - cur) > band
        cur = np.where(upd, pos[t], cur)
        held[t] = cur
    return held


def run(close, label, mom_lb, vol_lb=24, smooth=1, band=0.0):
    close = close.ffill().dropna(how="all")
    days = (close.index[-1] - close.index[0]).days or 1
    ppy = len(close) / days * 365.0
    ret = close.pct_change()
    vol = ret.rolling(vol_lb).std() * np.sqrt(ppy)
    sig = np.sign(close.pct_change(mom_lb))
    pos = (sig * (TARGET_VOL / vol.shift(1))).clip(-2, 2).fillna(0.0)
    if smooth > 1:
        pos = pos.ewm(span=smooth, min_periods=1).mean()
    P = apply_band(pos.values, band) if band > 0 else pos.values
    w = P / close.shape[1]
    fwd = ret.shift(-1).values
    m = np.isfinite(fwd).all(axis=1)
    W, F = w[m], fwd[m]
    gross = metrics.ann_ir(costs.net_returns(W, F, 0, 0), periods=ppy)
    turn = float(np.nanmean(np.abs(np.diff(W, axis=0, prepend=0)).sum(1)))
    irs = {b: metrics.ann_ir(costs.net_returns(W, F, b, 0)[np.isfinite(costs.net_returns(W, F, b, 0))], periods=ppy) for b in BPS_GRID}
    be = None
    for a, b in zip(BPS_GRID[:-1], BPS_GRID[1:]):
        if irs[a] >= 0 >= irs[b]:
            be = a + (b - a) * irs[a] / (irs[a] - irs[b] + 1e-12); break
    bestr = ("%.1f bps" % be) if be is not None else ("survives>%d" % BPS_GRID[-1] if irs[BPS_GRID[-1]] > 0 else "<0@0bps")
    print(f"{label:<42} grossIR {gross:+.2f} | turn/bar {turn:.3f} | break-even {bestr}")
    return be


if __name__ == "__main__":
    print("=== (a) TURNOVER REDUCTION on the ETF basket, 4h ===")
    e = fetch_1h(ETF); e4 = e.resample("4h").last()
    run(e4, "ETF 4h baseline (mom24, no band)", 24)
    run(e4, "ETF 4h slow (mom120)", 120)
    run(e4, "ETF 4h slow+smooth(span10)", 120, smooth=10)
    run(e4, "ETF 4h slow+smooth+band0.5", 120, smooth=10, band=0.5)
    run(e4, "ETF 4h slow+smooth+band1.0", 120, smooth=10, band=1.0)

    print("\n=== (b) CRYPTO 24/7 basket ===")
    c = fetch_1h(CRYPTO)
    print(f"   crypto assets: {list(c.columns)} ({len(c)} 1h bars)")
    c4 = c.resample("4h").last()
    run(c4, "CRYPTO 4h baseline (mom24)", 24)
    run(c4, "CRYPTO 4h slow (mom120)", 120)
    run(c4, "CRYPTO 4h slow+smooth+band0.5", 120, smooth=10, band=0.5)
    run(c4, "CRYPTO 1h slow+smooth+band0.5", 120, smooth=10, band=0.5) if False else None
    run(c, "CRYPTO 1h slow+smooth+band0.5", 240, smooth=10, band=0.5)

    print("\n=== (c) DAILY (deep history, the paper4-proven frame) ===")
    ed = fetch_daily(ETF)
    print(f"   ETF daily: {ed.shape[1]} assets, {len(ed)} bars, {ed.index[0].date()}..{ed.index[-1].date()}")
    run(ed, "ETF daily baseline (mom60)", 60, vol_lb=30)
    run(ed, "ETF daily slow+smooth+band0.3 (mom120)", 120, vol_lb=30, smooth=5, band=0.3)
    cd = fetch_daily(CRYPTO)
    print(f"   CRYPTO daily: {cd.shape[1]} assets, {len(cd)} bars")
    run(cd, "CRYPTO daily baseline (mom60)", 60, vol_lb=30)
    run(cd, "CRYPTO daily slow+smooth+band0.3 (mom120)", 120, vol_lb=30, smooth=5, band=0.3)
    print("\nCompare break-even to real eToro round-trip cost. >~20-30 bps would be encouraging.")
