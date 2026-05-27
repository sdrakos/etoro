"""Fetch S&P 500 + NASDAQ-100 constituents from Wikipedia, write JSON files.

Run from etoro/: `python back/scripts/build_universes.py`
"""
from __future__ import annotations
import json
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Wikipedia rejects requests without a real User-Agent (returns HTTP 403).
_opener = urllib.request.build_opener()
_opener.addheaders = [(
    "User-Agent",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
)]
urllib.request.install_opener(_opener)


def _normalize_ticker(t: str) -> str:
    # Polygon/Massive use dash for class shares: BRK-B not BRK.B
    return str(t).strip().replace(".", "-")


def build_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]  # first table = constituents
    tickers = []
    for _, row in df.iterrows():
        tickers.append({
            "ticker": _normalize_ticker(row["Symbol"]),
            "name": str(row["Security"]).strip(),
            "sector": str(row["GICS Sector"]).strip(),
        })
    out = {"as_of": date.today().isoformat(), "tickers": tickers}
    (DATA_DIR / "sp500.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"sp500.json - {len(tickers)} tickers")


def build_nasdaq100():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url)
    df = None
    for t in tables:
        cols = set(map(str, t.columns))
        if {"Ticker", "Company"}.issubset(cols) or {"Symbol", "Company"}.issubset(cols):
            df = t
            break
    if df is None:
        raise RuntimeError("Could not locate NASDAQ-100 constituents table on Wikipedia")
    ticker_col = "Ticker" if "Ticker" in df.columns else "Symbol"
    sector_col = next(
        (c for c in df.columns if any(k in str(c) for k in ("Sector", "GICS", "ICB Industry", "Industry"))),
        None,
    )
    tickers = []
    for _, row in df.iterrows():
        sector = str(row[sector_col]).strip() if sector_col else "Unknown"
        tickers.append({
            "ticker": _normalize_ticker(row[ticker_col]),
            "name": str(row["Company"]).strip(),
            "sector": sector,
        })
    out = {"as_of": date.today().isoformat(), "tickers": tickers}
    (DATA_DIR / "nasdaq100.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"nasdaq100.json - {len(tickers)} tickers")


if __name__ == "__main__":
    build_sp500()
    build_nasdaq100()
