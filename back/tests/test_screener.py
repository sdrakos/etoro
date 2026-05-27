"""Backend tests for GET /screener/{universe}.

All tests mock the Massive SDK; no real API calls.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_snapshot():
    """A snapshot_all-style response with 4 tickers."""
    def _snap(ticker, price, change_pct, volume):
        return MagicMock(
            ticker=ticker,
            day=MagicMock(close=price, volume=volume),
            todays_change_perc=change_pct,
            last_trade=MagicMock(price=price),
        )
    return [
        _snap("AAPL", 180.0, 1.5, 50_000_000),
        _snap("MSFT", 400.0, -0.5, 25_000_000),
        _snap("JPM", 200.0, 0.3, 10_000_000),
        _snap("TSLA", 250.0, 2.1, 80_000_000),
    ]


@pytest.fixture
def client(tmp_path, monkeypatch, fake_snapshot):
    """FastAPI TestClient with patched universe loader + snapshot."""
    monkeypatch.setattr("routers.screener.DATA_DIR", FIXTURE_DIR)
    monkeypatch.setattr("routers.screener.METADATA_DB", tmp_path / "metadata.db")
    from routers import screener
    screener._snapshot_memo.clear()
    screener._load_universe_file.cache_clear()

    fake_client = MagicMock()
    fake_client.get_snapshot_all.return_value = fake_snapshot
    fake_client.get_ticker_details.return_value = MagicMock(market_cap=1_000_000_000)
    fake_client.list_ratios.return_value = iter([MagicMock(price_to_earnings_ratio=20.0)])

    monkeypatch.setattr("routers.screener.get_client", lambda: fake_client)

    from main import app
    return TestClient(app), fake_client


def test_sp500_endpoint_returns_rows(client):
    tc, _ = client
    resp = tc.get("/screener/sp500")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 3
    tickers = {r["ticker"] for r in rows}
    assert tickers == {"AAPL", "MSFT", "JPM"}


def test_nasdaq100_endpoint_returns_rows(client):
    tc, _ = client
    resp = tc.get("/screener/nasdaq100")
    assert resp.status_code == 200
    tickers = {r["ticker"] for r in resp.json()}
    assert tickers == {"AAPL", "MSFT", "TSLA"}


def test_combined_universe_dedups_overlap(client):
    tc, _ = client
    resp = tc.get("/screener/combined")
    assert resp.status_code == 200
    tickers = [r["ticker"] for r in resp.json()]
    assert sorted(tickers) == ["AAPL", "JPM", "MSFT", "TSLA"]
    assert len(tickers) == len(set(tickers))


def test_unknown_universe_returns_404(client):
    tc, _ = client
    resp = tc.get("/screener/foo")
    assert resp.status_code == 404


def test_snapshot_memo_shared_across_universes(client):
    tc, fake = client
    tc.get("/screener/sp500")
    tc.get("/screener/nasdaq100")
    assert fake.get_snapshot_all.call_count == 1


def test_missing_snapshot_returns_nulls(tmp_path, monkeypatch):
    """Ticker exists in universe JSON but absent from snapshot → null price, no exception."""
    monkeypatch.setattr("routers.screener.DATA_DIR", FIXTURE_DIR)
    monkeypatch.setattr("routers.screener.METADATA_DB", tmp_path / "metadata.db")
    from routers import screener as s
    s._snapshot_memo.clear()
    s._load_universe_file.cache_clear()

    fake_client = MagicMock()
    fake_client.get_snapshot_all.return_value = [
        MagicMock(ticker="AAPL", day=MagicMock(close=180.0, volume=1_000_000),
                  todays_change_perc=1.0)
    ]
    fake_client.get_ticker_details.return_value = MagicMock(market_cap=None)
    fake_client.list_ratios.return_value = iter([])

    monkeypatch.setattr("routers.screener.get_client", lambda: fake_client)

    from main import app
    tc = TestClient(app)
    rows = tc.get("/screener/sp500").json()
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["AAPL"]["price"] == 180.0
    assert by_ticker["MSFT"]["price"] is None
    assert by_ticker["JPM"]["price"] is None
