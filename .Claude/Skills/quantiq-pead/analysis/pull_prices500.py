#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull Yahoo adjusted-close panel (2015-2024) for the ~500 S&P names in sp500_5yr.csv.
Bars-only (fast). Survivors return data; delisted/renamed tickers are skipped.
Writes prices500.csv (date x ticker) for the big-universe + long-window lead-lag run."""
import sys, os, warnings, datetime as dt
from datetime import date
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ETORO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ETORO)
from trader.data.sources.yahoo import fetch_bars

tickers = sorted(pd.read_csv(os.path.join(ETORO, "paper1_RL", "sp500_5yr.csv"))["Name"].unique())
print(f"[universe] {len(tickers)} candidate tickers")

start, end = date(2015, 1, 1), date(2024, 12, 31)
series = {}
ok = fail = 0
for i, tk in enumerate(tickers):
    try:
        rows = fetch_bars(tk, start, end, "day")
        if len(rows) < 1000:            # need decent coverage over 2015-2024
            fail += 1; continue
        idx = [dt.datetime.utcfromtimestamp(r["timestamp"]/1000).strftime("%Y-%m-%d") for r in rows]
        series[tk] = pd.Series([r["close"] for r in rows], index=idx)
        ok += 1
    except Exception:
        fail += 1
    if (i+1) % 50 == 0:
        print(f"  {i+1}/{len(tickers)} (ok={ok} fail={fail})")

df = pd.DataFrame(series).sort_index()
df = df[df.columns[df.notna().mean() >= 0.95]]      # keep well-covered names
df.index.name = "date"
df.to_csv(os.path.join(HERE, "prices500.csv"))
print(f"[done] prices500.csv {df.shape[0]} days x {df.shape[1]} tickers "
      f"({df.index[0]} -> {df.index[-1]})")
