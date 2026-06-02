from datetime import date
from unittest import mock
import trader.data.loader as loader


def _two_bars(ticker):
    return [
        {"ticker": ticker, "timestamp": 1_704_153_600_000,
         "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1000, "vwap": None},
        {"ticker": ticker, "timestamp": 1_704_240_000_000,
         "open": 11, "high": 13, "low": 10, "close": 12, "volume": 2000, "vwap": None},
    ]


def test_load_bars_uses_yahoo_source(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DB", tmp_path / "cache.db")
    with mock.patch.object(loader.yahoo, "fetch_bars",
                           return_value=_two_bars("AAPL")) as y, \
         mock.patch.object(loader.massive, "fetch_bars") as m:
        df = loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3),
                              source="yahoo")
    assert y.called
    assert not m.called
    assert len(df) == 2


def test_load_bars_is_cache_aside(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DB", tmp_path / "cache.db")
    with mock.patch.object(loader.yahoo, "fetch_bars",
                           return_value=_two_bars("AAPL")) as y:
        loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="yahoo")
        loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="yahoo")
    assert y.call_count == 1  # second call served entirely from cache


def test_load_bars_rejects_unknown_source(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DB", tmp_path / "cache.db")
    import pytest
    with pytest.raises(ValueError):
        loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="bogus")
