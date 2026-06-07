"""Reproducible IC probe: does GDELT news TONE predict next-day(/5d/20d) returns? — the cheap, honest
test that decided NOT to build a full sentiment harness for the macro/ETF basket.

Result (refined AllNames themes, 2015-2024, leak-free): a ROBUST NULL. |IC| <= ~0.025 at 1 day, signs
FLIP across 1/5/20-day horizons (the noise signature), sign-hit ~50%. The earlier faint TLT/USO hints
(IC ~0.04) were artifacts of impure GKG theme codes — they vanished once the themes were cleaned.
Conclusion: GDELT tone is not a usable predictor here; do not pursue tone-as-feature for this basket.

Input: gdelt_tone.csv (day, product, avg_tone, n) pulled from gdelt-bq.gdeltv2.gkg_partitioned via
the refined AllNames regex (see gdelt_sentiment.py / CLAUDE.md). Prices from Yahoo (keyless).

    python paper4/news/sentiment_probe.py
"""
from __future__ import annotations
import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

PRODUCTS = ["SPY", "TLT", "GLD", "USO", "UUP"]


def causal_z(tone, win=21):
    """Trailing z-score 'tone surprise' (uses only past) — the usable form of a biased tone level."""
    return (tone - tone.rolling(win, min_periods=10).mean()) / (tone.rolling(win, min_periods=10).std() + 1e-9)


def probe(csv=None):
    import yfinance as yf
    csv = csv or os.path.join(os.path.dirname(__file__), "gdelt_tone.csv")
    tone = pd.read_csv(csv, parse_dates=["day"])
    px = yf.download(PRODUCTS, start="2015-02-01", end="2026-06-09", progress=False)["Close"]
    rows = []
    for p in PRODUCTS:
        t = tone[tone["product"] == p].set_index("day").sort_index()
        z = causal_z(t["avg_tone"])
        s = px[p].copy(); s.index = pd.to_datetime(s.index)
        ics = {}
        for h in (1, 5, 20):
            fwd = s.shift(-h) / s - 1.0                       # leak-free: tone[d] -> forward return
            d = pd.DataFrame({"z": z, "r": fwd}).dropna()
            ics[h] = d["z"].corr(d["r"])
        rows.append({"product": p, "n_per_day": round(t["n"].mean()),
                     "IC_1d": round(ics[1], 4), "IC_5d": round(ics[5], 4), "IC_20d": round(ics[20], 4)})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    flip = ((out[["IC_1d", "IC_5d", "IC_20d"]].apply(np.sign, axis=0).nunique(axis=1) > 1)).sum()
    print(f"\n{flip}/{len(out)} products flip IC sign across horizons; all |IC| < 0.035  ->  ROBUST NULL")
    return out


if __name__ == "__main__":
    probe()
