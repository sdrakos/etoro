"""Screener backend tests — eToro price source (mocked). No real API calls."""
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient


def _discover_page(items, page, page_size, total):
    return {"page": page, "pageSize": page_size, "totalItems": total, "items": items}


class FakeEtoro:
    """Routes EtoroClient.request by path: discover (paged) + rates (by ids)."""
    def __init__(self, instruments, rates):
        self._instruments = instruments  # list of discover item dicts
        self._rates = rates              # {instrumentID: {bid,ask,lastExecution}}
        self.calls = []

    def request(self, method, path, *, params=None, json=None):
        self.calls.append((method, path, params))
        if path == "/api/v1/instruments/discover":
            page = int(params.get("page", 1))
            size = int(params.get("pageSize", 1000))
            start = (page - 1) * size
            items = self._instruments[start:start + size]
            return _discover_page(items, page, size, len(self._instruments))
        if path == "/api/v1/market-data/instruments/rates":
            ids = params["instrumentIds"]
            ids = ids if isinstance(ids, list) else [ids]
            rates = [dict(instrumentID=int(i), **self._rates[int(i)])
                     for i in ids if int(i) in self._rates]
            return {"rates": rates}
        raise AssertionError(f"unexpected path {path}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()

    instruments = [
        {"instrumentId": 1001, "symbol": "AAPL", "displayname": "Apple",
         "internalExchangeName": "NASDAQ", "exchangeID": 4,
         "dailyPriceChange": 1.5, "buyHoldingPct": 82.0, "isExchangeOpen": True},
        {"instrumentId": 1002, "symbol": "MSFT", "displayname": "Microsoft",
         "internalExchangeName": "NASDAQ", "exchangeID": 4,
         "dailyPriceChange": -0.7, "buyHoldingPct": 65.0, "isExchangeOpen": True},
    ]
    rates = {
        1001: {"bid": 213.5, "ask": 213.7, "lastExecution": 213.6},
        1002: {"bid": 401.0, "ask": 401.2, "lastExecution": 401.1},
    }
    fake = FakeEtoro(instruments, rates)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    monkeypatch.setattr(screener, "_load_universe", lambda u: [
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Tech"},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Tech"},
        {"ticker": "NOPE", "name": "Unmapped Co.", "sector": "X"},
    ])

    from main import app
    return TestClient(app), fake


def test_refresh_catalog_populates(client):
    tc, _ = client
    r = tc.post("/screener/refresh-etoro-catalog")
    assert r.status_code == 200
    assert r.json()["instruments"] == 2


def test_screener_uses_live_etoro_prices(client):
    tc, _ = client
    tc.post("/screener/refresh-etoro-catalog")
    r = tc.get("/screener/sp500")
    assert r.status_code == 200
    rows = {row["ticker"]: row for row in r.json()}
    aapl = rows["AAPL"]
    assert aapl["price"] == 213.6
    assert aapl["sell"] == 213.5
    assert aapl["buy"] == 213.7
    assert aapl["change_pct"] == 1.5
    assert aapl["sentiment_buy_pct"] == 82.0
    assert aapl["exchange"] == "NASDAQ"
    assert aapl["instrument_id"] == 1001
    assert rows["NOPE"]["price"] is None


def test_screener_sp500_ok(client):
    tc, _ = client
    r = tc.get("/screener/sp500")
    assert r.status_code == 200
