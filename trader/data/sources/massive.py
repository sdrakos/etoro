"""Massive/Polygon source via the REST SDK. Daily aggregate bars."""
from __future__ import annotations
from datetime import date
from functools import lru_cache

from trader.config import get_massive_key

try:
    from massive import RESTClient
except ImportError:
    from polygon import RESTClient


@lru_cache(maxsize=1)
def _client() -> "RESTClient":
    return RESTClient(api_key=get_massive_key())


def fetch_bars(ticker: str, start: date, end: date,
               timespan: str = "day") -> list[dict]:
    """Return daily bar dicts ready for Cache.upsert()."""
    bars = list(_client().list_aggs(
        ticker, 1, timespan,
        start.isoformat(), end.isoformat(),
        limit=50000,
    ))
    return [{
        "ticker": ticker, "timestamp": b.timestamp,
        "open": b.open, "high": b.high, "low": b.low, "close": b.close,
        "volume": b.volume, "vwap": getattr(b, "vwap", None),
    } for b in bars]
