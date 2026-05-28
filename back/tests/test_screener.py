"""Backend tests for GET /screener/{universe}.

All tests mock the Massive SDK; no real API calls.

After the Basic-tier compatibility refactor, the screener uses
get_grouped_daily_aggs (free) twice — once for the latest business day
and once for the day before — to compute price and change_pct. Tests
mock both calls in chronological order (newer date first, older second).
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _agg(ticker, close, volume):
    """A grouped_daily_aggs-style row."""
    return MagicMock(ticker=ticker, close=close, volume=volume)


@pytest.fixture
def fake_today_aggs():
    return [
        _agg("AAPL", 180.0, 50_000_000),
        _agg("MSFT", 400.0, 25_000_000),
        _agg("JPM", 200.0, 10_000_000),
        _agg("TSLA", 250.0, 80_000_000),
    ]


@pytest.fixture
def fake_prev_aggs():
    # ~1% lower than today, gives clean change_pct in tests
    return [
        _agg("AAPL", 178.2, 49_500_000),
        _agg("MSFT", 402.0, 25_100_000),
        _agg("JPM", 199.4, 10_050_000),
        _agg("TSLA", 244.9, 78_000_000),
    ]


@pytest.fixture
def client(tmp_path, monkeypatch, fake_today_aggs, fake_prev_aggs):
    """FastAPI TestClient with patched universe loader + grouped daily."""
    monkeypatch.setattr("routers.screener.DATA_DIR", FIXTURE_DIR)
    monkeypatch.setattr("routers.screener.METADATA_DB", tmp_path / "metadata.db")
    from routers import screener
    screener._snapshot_memo.clear()
    screener._load_universe_file.cache_clear()

    fake_client = MagicMock()
    # The router asks for the most-recent business day first, then the one
    # before. The loop walks backwards day-by-day so we feed an iterator
    # that returns today first, prev second, then empty (defensive).
    fake_client.get_grouped_daily_aggs.side_effect = [
        fake_today_aggs,
        fake_prev_aggs,
    ]
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
    # change_pct populated from (today - prev) / prev
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["AAPL"]["price"] == 180.0
    assert by_ticker["AAPL"]["change_pct"] == pytest.approx(1.0101, rel=1e-3)


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


def test_grouped_daily_memo_shared_across_universes(client):
    tc, fake = client
    tc.get("/screener/sp500")
    tc.get("/screener/nasdaq100")
    # 2 calls total (today + prev) — NOT 4 — proves memo works across universes
    assert fake.get_grouped_daily_aggs.call_count == 2


def test_missing_today_row_returns_nulls(tmp_path, monkeypatch, fake_prev_aggs):
    """Ticker exists in universe JSON but absent from today's grouped aggs → null price."""
    monkeypatch.setattr("routers.screener.DATA_DIR", FIXTURE_DIR)
    monkeypatch.setattr("routers.screener.METADATA_DB", tmp_path / "metadata.db")
    from routers import screener as s
    s._snapshot_memo.clear()
    s._load_universe_file.cache_clear()

    fake_client = MagicMock()
    # Only AAPL present today; MSFT/JPM missing
    fake_client.get_grouped_daily_aggs.side_effect = [
        [_agg("AAPL", 180.0, 1_000_000)],
        fake_prev_aggs,
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


def test_screener_does_not_call_metadata_endpoints_inline(client):
    """Inline screener requests must NOT hit get_ticker_details / list_ratios.

    Those are rate-limited on Basic tier — refreshing 500 rows would take
    100+ minutes. Metadata must be cached out-of-band.
    """
    tc, fake = client
    tc.get("/screener/sp500")
    assert fake.get_ticker_details.call_count == 0
    assert fake.list_ratios.call_count == 0


def test_cached_metadata_surfaces_in_response(tmp_path, monkeypatch,
                                               fake_today_aggs, fake_prev_aggs):
    """If MetadataCache already has rows, those values appear in the response."""
    db = tmp_path / "metadata.db"
    monkeypatch.setattr("routers.screener.DATA_DIR", FIXTURE_DIR)
    monkeypatch.setattr("routers.screener.METADATA_DB", db)
    from routers import screener as s
    s._snapshot_memo.clear()
    s._load_universe_file.cache_clear()

    # Pre-populate the cache
    from data_cache.metadata_cache import MetadataCache
    cache = MetadataCache(db)
    cache.put("AAPL", market_cap=2_800_000_000_000, pe_ratio=28.5)

    fake_client = MagicMock()
    fake_client.get_grouped_daily_aggs.side_effect = [fake_today_aggs, fake_prev_aggs]
    monkeypatch.setattr("routers.screener.get_client", lambda: fake_client)

    from main import app
    tc = TestClient(app)
    rows = tc.get("/screener/sp500").json()
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["AAPL"]["market_cap"] == 2_800_000_000_000
    assert by_ticker["AAPL"]["pe_ratio"] == 28.5
    # MSFT was not pre-cached → still null
    assert by_ticker["MSFT"]["market_cap"] is None
    assert by_ticker["MSFT"]["pe_ratio"] is None
