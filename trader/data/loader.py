"""Cache-aside loader: SQLite first, fetch missing range from Massive API."""
from __future__ import annotations
import datetime as dt
import logging
from datetime import date
from functools import lru_cache
from typing import Optional
import pandas as pd

from trader.config import CACHE_DB, MASSIVE_KEY
from trader.data.cache import Cache

log = logging.getLogger(__name__)

try:
    from massive import RESTClient
except ImportError:
    from polygon import RESTClient


@lru_cache(maxsize=1)
def _client() -> RESTClient:
    return RESTClient(api_key=MASSIVE_KEY)


def _to_ms(d: date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _gaps(coverage: Optional[tuple[int, int]], start_ms: int, end_ms: int) -> list[tuple[int, int]]:
    """Return list of (start_ms, end_ms) ranges the cache does NOT cover."""
    if coverage is None:
        return [(start_ms, end_ms)]
    cmin, cmax = coverage
    gaps = []
    if start_ms < cmin:
        gaps.append((start_ms, min(end_ms, cmin - 1)))
    if end_ms > cmax:
        gaps.append((max(start_ms, cmax + 1), end_ms))
    return gaps


def load_bars(ticker: str, start: date, end: date,
              timespan: str = "day") -> pd.DataFrame:
    """Cache-aside fetch. Returns DataFrame indexed by datetime (UTC)."""
    if timespan != "day":
        raise NotImplementedError(
            f"Only timespan='day' is supported in Phase 1 (got {timespan!r}). "
            "Intraday support requires datetime-precision gap calculation."
        )
    cache = Cache(CACHE_DB)
    start_ms, end_ms = _to_ms(start), _to_ms(end)

    coverage = cache.coverage(ticker, timespan)
    gaps = _gaps(coverage, start_ms, end_ms)

    for gap_start, gap_end in gaps:
        log.info("Fetching %s %s..%s from Massive", ticker, gap_start, gap_end)
        bars = list(_client().list_aggs(
            ticker, 1, timespan,
            dt.datetime.fromtimestamp(gap_start / 1000, tz=dt.timezone.utc).date().isoformat(),
            dt.datetime.fromtimestamp(gap_end / 1000, tz=dt.timezone.utc).date().isoformat(),
            limit=50000,
        ))
        rows = [{"ticker": ticker, "timestamp": b.timestamp,
                 "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                 "volume": b.volume, "vwap": getattr(b, "vwap", None)} for b in bars]
        if rows:
            cache.upsert(rows, timespan=timespan)

    df = cache.query(ticker, start_ms, end_ms, timespan=timespan)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("datetime").drop(columns=["timestamp"])
