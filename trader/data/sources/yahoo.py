"""Yahoo Finance source via yfinance (free, no API key). Adjusted daily bars."""
from __future__ import annotations
import datetime as dt
from datetime import date, timedelta

import yfinance as yf


def fetch_bars(ticker: str, start: date, end: date,
               timespan: str = "day") -> list[dict]:
    """Return adjusted daily bar dicts ready for Cache.upsert().

    `end` is inclusive here; yfinance treats its `end` as exclusive, so we add
    one day. Timestamps are anchored to UTC midnight to match the cache convention.
    """
    if timespan != "day":
        raise NotImplementedError("Yahoo source supports timespan='day' only.")
    df = yf.Ticker(ticker).history(
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=True,
    )
    rows: list[dict] = []
    for idx, row in df.iterrows():
        ts = int(dt.datetime(idx.year, idx.month, idx.day,
                             tzinfo=dt.timezone.utc).timestamp() * 1000)
        rows.append({
            "ticker": ticker, "timestamp": ts,
            "open": float(row["Open"]), "high": float(row["High"]),
            "low": float(row["Low"]), "close": float(row["Close"]),
            "volume": float(row["Volume"]), "vwap": None,
        })
    return rows
