from datetime import date
from unittest.mock import patch
import pytest

from trader.data.cache import Cache
from trader.data.loader import load_bars


def _ms(d: date) -> int:
    import datetime as dt
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def test_cache_hit_skips_api(temp_db, monkeypatch):
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 2)),
         "open": 100, "high": 101, "low": 99, "close": 100.5,
         "volume": 1_000_000, "vwap": 100.2},
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 3)),
         "open": 101, "high": 103, "low": 100, "close": 102,
         "volume": 1_200_000, "vwap": 101.8},
    ], source="massive")
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)
    with patch("trader.data.loader.massive.fetch_bars") as fetch:
        df = load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="massive")
    assert len(df) == 2
    assert fetch.call_count == 0


def test_partial_gap_fetches_delta_only(temp_db, monkeypatch):
    """Cache has Jan 2024. Request Jan 2023..Feb 2024 — must fetch only the missing left+right slices."""
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 2)),
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "vwap": 1},
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 31)),
         "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "vwap": 2},
    ], source="massive")
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)

    with patch("trader.data.loader.massive.fetch_bars", return_value=[]) as fetch:
        load_bars("AAPL", date(2023, 1, 1), date(2024, 2, 28), source="massive")

    # Two source calls: left gap (2023-01-01..2024-01-01) + right gap (2024-02-01..2024-02-28)
    assert fetch.call_count == 2

    # Verify the date boundaries passed to the source — gap math is the
    # easiest thing to regress and the most consequential.
    # Each call: fetch_bars(ticker, start_date, end_date, timespan)
    call_args = [call.args for call in fetch.call_args_list]
    iso_ranges = [(a[1].isoformat(), a[2].isoformat()) for a in call_args]
    iso_ranges.sort()
    # Left gap: starts 2023-01-01, ends at or before cmin date
    assert iso_ranges[0][0] == "2023-01-01"
    assert iso_ranges[0][1] <= "2024-01-02"
    # Right gap: starts at or after cmax date, ends 2024-02-28
    assert iso_ranges[1][0] >= "2024-01-31"
    assert iso_ranges[1][1] == "2024-02-28"


def test_unknown_ticker_returns_empty(temp_db, monkeypatch):
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)
    with patch("trader.data.loader.massive.fetch_bars", return_value=[]):
        df = load_bars("ZZZZ", date(2024, 1, 1), date(2024, 1, 5), source="massive")
    assert df.empty


def test_intraday_timespan_raises(temp_db, monkeypatch):
    """Phase 1 explicitly rejects intraday — guard against latent gap bug."""
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)
    with pytest.raises(NotImplementedError, match="timespan='day'"):
        load_bars("AAPL", date(2024, 1, 1), date(2024, 1, 5), timespan="minute")
