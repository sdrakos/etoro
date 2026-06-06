"""Cache-aside (T,N) close matrix for the paper4 universe (Yahoo daily, keyless).
Numeric arrays -> npz; ticker/date metadata -> JSON sidecar. No pickle."""
from __future__ import annotations
import os, sys, json, warnings
from datetime import date
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from trader.data.sources.yahoo import fetch_bars   # noqa: E402
from universe import TICKERS, START, END           # noqa: E402  (run from paper4/code)


def load_close_matrix(cache_path="paper4_close.npz"):
    side = cache_path + ".json"
    if os.path.exists(cache_path) and os.path.exists(side):
        z = np.load(cache_path)
        with open(side, encoding="utf-8") as f:
            meta = json.load(f)
        return z["close"], z["dates"], meta["tickers"]

    start, end = date.fromisoformat(START), date.fromisoformat(END)
    per = {}
    for tk in TICKERS:
        try:
            per[tk] = {r["timestamp"]: r["close"] for r in fetch_bars(tk, start, end, "day")}
        except Exception as e:
            warnings.warn(f"bars {tk}: {e}")
    all_ts = sorted(set().union(*[set(d) for d in per.values()]))
    tickers = [t for t in TICKERS if t in per and len(per[t]) > 252]
    T, N = len(all_ts), len(tickers)
    idx = {ts: i for i, ts in enumerate(all_ts)}
    close = np.full((T, N), np.nan)
    for j, tk in enumerate(tickers):
        for ts, c in per[tk].items():
            close[idx[ts], j] = c
    dates = np.array(all_ts)
    np.savez(cache_path, close=close, dates=dates)
    with open(side, "w", encoding="utf-8") as f:
        json.dump({"tickers": tickers}, f)
    return close, dates, tickers
