"""Cache-aside (T,N) close matrix for the paper4 ETF basket (Yahoo daily, keyless).
Numeric arrays -> npz; ticker metadata -> JSON sidecar. No pickle."""
from __future__ import annotations
import os, sys, json, warnings
from datetime import date
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from trader.data.sources.yahoo import fetch_bars   # noqa: E402
from etf_universe import TICKERS, START, END        # noqa: E402  (run from paper4/code)


def _ffill(close):
    out = close.copy()
    for j in range(out.shape[1]):
        last = np.nan
        for i in range(len(out)):
            if np.isnan(out[i, j]):
                out[i, j] = last
            else:
                last = out[i, j]
    return out


def load_etf_matrix(cache_path="etf_close.npz", fill=True):
    """Return (close (T,N), dates (T,), tickers list). Forward-filled when fill=True."""
    side = cache_path + ".json"
    if os.path.exists(cache_path) and os.path.exists(side):
        z = np.load(cache_path)
        with open(side, encoding="utf-8") as f:
            tickers = json.load(f)["tickers"]
        close = z["close"]
        return (_ffill(close) if fill else close), z["dates"], tickers

    start, end = date.fromisoformat(START), date.fromisoformat(END)
    per = {}
    for tk in TICKERS:
        try:
            rows = fetch_bars(tk, start, end, "day")
            if len(rows) > 1500:
                per[tk] = {r["timestamp"]: r["close"] for r in rows}
        except Exception as e:
            warnings.warn(f"bars {tk}: {e}")
    all_ts = sorted(set().union(*[set(d) for d in per.values()]))
    tickers = [t for t in TICKERS if t in per]
    idx = {ts: i for i, ts in enumerate(all_ts)}
    close = np.full((len(all_ts), len(tickers)), np.nan)
    for j, tk in enumerate(tickers):
        for ts, c in per[tk].items():
            close[idx[ts], j] = c
    dates = np.array(all_ts)
    np.savez(cache_path, close=close, dates=dates)
    with open(side, "w", encoding="utf-8") as f:
        json.dump({"tickers": tickers}, f)
    return (_ffill(close) if fill else close), dates, tickers
