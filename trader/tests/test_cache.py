import sqlite3
import pandas as pd
import pytest

from trader.data.cache import Cache


def test_init_creates_schema(temp_db):
    cache = Cache(temp_db)
    with sqlite3.connect(temp_db) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
    assert "bars" in tables


def test_upsert_idempotent(temp_db):
    cache = Cache(temp_db)
    bar = {"ticker": "AAPL", "timestamp": 1700000000000,
           "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0,
           "volume": 1_000_000.0, "vwap": 100.5}
    cache.upsert([bar])
    cache.upsert([bar])  # same row twice
    df = cache.query("AAPL", start_ms=0, end_ms=1_800_000_000_000)
    assert len(df) == 1
    assert df.iloc[0]["close"] == 101.0


def test_query_unknown_ticker_returns_empty(temp_db):
    cache = Cache(temp_db)
    df = cache.query("ZZZZ", 0, 2_000_000_000_000)
    assert df.empty


def test_coverage_ranges_after_insert(temp_db):
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": 1_700_000_000_000,
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "vwap": 1},
        {"ticker": "AAPL", "timestamp": 1_700_086_400_000,
         "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "vwap": 2},
    ])
    coverage = cache.coverage("AAPL")
    assert coverage == (1_700_000_000_000, 1_700_086_400_000)


def test_coverage_unknown_ticker_returns_none(temp_db):
    cache = Cache(temp_db)
    assert cache.coverage("ZZZZ") is None


def test_upsert_empty_returns_zero(temp_db):
    cache = Cache(temp_db)
    assert cache.upsert([]) == 0


def test_clear_removes_ticker(temp_db):
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": 1_700_000_000_000,
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "vwap": 1},
    ])
    deleted = cache.clear("AAPL")
    assert deleted == 1
    assert cache.coverage("AAPL") is None


def test_list_tickers_returns_summary(temp_db):
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": 1_700_000_000_000,
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "vwap": 1},
        {"ticker": "MSFT", "timestamp": 1_700_086_400_000,
         "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "vwap": 2},
    ])
    df = cache.list_tickers()
    assert list(df["ticker"]) == ["AAPL", "MSFT"]
    assert int(df.iloc[0]["bar_count"]) == 1
