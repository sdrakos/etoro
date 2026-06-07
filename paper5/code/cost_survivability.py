#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper5 Phase-2 probe: COST-SURVIVABILITY of intraday time-series momentum.

Before building any DMN we ask the only question that matters for intraday: does a simple,
vol-targeted TSMOM baseline survive realistic costs at 1h and 4h? We sweep the spread (bps)
and report the BREAK-EVEN cost (where net IR crosses 0). Faster frame = more turnover = more
cost. Leak-free: vol & signal use only the past; entry is next-bar. Reuses paper4 cost/metrics.
Data: free Yahoo intraday (yfinance, ~730d of 1h bars); 4h resampled from 1h.
"""
import sys, os
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import yfinance as yf

BASKET = ["SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE"]  # diversified
VOL_LB = 24          # bars for trailing vol
MOM_LB = 24          # bars for trailing-return TSMOM sign
TARGET_VOL = 0.15    # annualized per-asset vol target
BPS_GRID = [0, 1, 2, 5, 10, 15, 20, 30, 50]


def fetch_1h(tickers):
    df = yf.download(tickers, period="730d", interval="1h", auto_adjust=True,
                     progress=False, group_by="ticker")
    cols = {}
    for t in tickers:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 1000:
                cols[t] = s
        except Exception:
            pass
    return pd.DataFrame(cols).sort_index()


def run_frame(close, label):
    close = close.ffill().dropna(how="all")
    # bars/day -> annualization
    days = (close.index[-1] - close.index[0]).days or 1
    ppy = len(close) / days * 365.0
    ret = close.pct_change()
    vol = ret.rolling(VOL_LB).std() * np.sqrt(ppy)          # causal annualized vol
    sig = np.sign(close.pct_change(MOM_LB))                  # TSMOM trend sign (causal)
    pos = (sig * (TARGET_VOL / vol.shift(1))).clip(-2, 2).fillna(0.0)  # vol-scaled, prior-bar vol
    w = pos.div(close.shape[1])                             # equal-weight basket
    fwd = ret.shift(-1)                                     # next-bar return (no look-ahead)
    m = np.isfinite(fwd.values).all(axis=1)
    W, F = w.values[m], fwd.values[m]

    gross = metrics.ann_ir(costs.net_returns(W, F, spread_bps=0, short_fin_bps_annual=0), periods=ppy)
    turn = float(np.nanmean(np.abs(np.diff(W, axis=0, prepend=0)).sum(1)))
    irs = {}
    for bps in BPS_GRID:
        net = costs.net_returns(W, F, spread_bps=bps, short_fin_bps_annual=0)
        irs[bps] = metrics.ann_ir(net[np.isfinite(net)], periods=ppy)
    # break-even bps (linear interp where IR crosses 0)
    be = None
    xs = BPS_GRID
    for a, b in zip(xs[:-1], xs[1:]):
        if irs[a] >= 0 >= irs[b]:
            be = a + (b - a) * irs[a] / (irs[a] - irs[b] + 1e-12); break
    print(f"\n=== {label}  ({len(close)} bars, ~{ppy:.0f}/yr, {close.shape[1]} assets) ===")
    print(f"gross IR {gross:.2f} | avg turnover/bar {turn:.3f} | ann turnover ~{turn*ppy:.0f}")
    print("  bps:  " + "  ".join(f"{b}:{irs[b]:+.2f}" for b in BPS_GRID))
    print(f"  >>> break-even spread = {('%.1f bps' % be) if be is not None else 'survives all tested' if irs[BPS_GRID[-1]]>0 else '<0 even at 0bps'}")
    return be


if __name__ == "__main__":
    print("Fetching Yahoo 1h (~730d)...")
    c1 = fetch_1h(BASKET)
    print(f"got {c1.shape[1]} assets, {len(c1)} 1h bars, {c1.index[0].date()}..{c1.index[-1].date()}")
    run_frame(c1, "1h")
    c4 = c1.resample("4h").last()
    run_frame(c4, "4h")
    c1d = c1.resample("1D").last()
    run_frame(c1d, "1D (daily, reference)")
    print("\nVerdict: compare break-even bps to eToro's real ~round-trip 4h cost (spread+overnight).")
