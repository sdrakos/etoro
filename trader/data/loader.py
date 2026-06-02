"""Cache-aside loader: SQLite first, fetch missing range from the chosen source."""
from __future__ import annotations
import datetime as dt
import logging
from datetime import date
from typing import Optional
import pandas as pd

from trader.config import CACHE_DB
from trader.data.cache import Cache
from trader.data.sources import massive, yahoo

log = logging.getLogger(__name__)

_SOURCES = {"yahoo": yahoo, "massive": massive}


def _to_ms(d: date) -> int:
    return int(dt.datetime(d.year, d.month, d.day,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


def _gaps(coverage: Optional[tuple[int, int]],
          start_ms: int, end_ms: int) -> list[tuple[int, int]]:
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
              timespan: str = "day", source: str = "yahoo") -> pd.DataFrame:
    """Cache-aside fetch from `source`. Returns DataFrame indexed by datetime (UTC)."""
    if timespan != "day":
        raise NotImplementedError(
            f"Only timespan='day' is supported in Phase 1 (got {timespan!r}). "
            "Intraday support requires datetime-precision gap calculation."
        )
    try:
        provider = _SOURCES[source]
    except KeyError:
        raise ValueError(
            f"unknown source: {source!r}. Choose from {sorted(_SOURCES)}."
        )

    cache = Cache(CACHE_DB)
    start_ms, end_ms = _to_ms(start), _to_ms(end)

    coverage = cache.coverage(ticker, timespan, source)
    gaps = _gaps(coverage, start_ms, end_ms)

    for gap_start, gap_end in gaps:
        gs = dt.datetime.fromtimestamp(gap_start / 1000, tz=dt.timezone.utc).date()
        ge = dt.datetime.fromtimestamp(gap_end / 1000, tz=dt.timezone.utc).date()
        log.info("Fetching %s %s..%s from %s", ticker, gs, ge, source)
        rows = provider.fetch_bars(ticker, gs, ge, timespan)
        if rows:
            cache.upsert(rows, timespan=timespan, source=source)

    df = cache.query(ticker, start_ms, end_ms, timespan=timespan, source=source)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("datetime").drop(columns=["timestamp"])
