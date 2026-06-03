"""Screener backend tests — eToro price source (mocked, real API shapes)."""
import pytest
from fastapi.testclient import TestClient


class FakeEtoro:
    """Routes EtoroClient.request by path: discover (paged, lean), rates, closing-price."""
    def __init__(self, instruments, rates, closing):
        self._instruments = instruments  # lean discover items
        self._rates = rates              # {id: {bid,ask,lastExecution}}
        self._closing = closing          # {id: {officialClosingPrice, isMarketOpen}}
        self.calls = []

    def request(self, method, path, *, params=None, json=None):
        self.calls.append((method, path, params))
        if path == "/api/v1/instruments/discover":
            page = int(params.get("page", 1)); size = int(params.get("pageSize", 1000))
            start = (page - 1) * size
            items = self._instruments[start:start + size]
            return {"page": page, "pageSize": size, "totalItems": len(self._instruments), "items": items}
        if path == "/api/v1/market-data/instruments/rates":
            ids = params["instrumentIds"]; ids = ids if isinstance(ids, list) else [ids]
            return {"rates": [dict(instrumentID=int(i), **self._rates[int(i)])
                              for i in ids if int(i) in self._rates]}
        if path == "/api/v1/market-data/instruments/history/closing-price":
            return [dict(instrumentId=i, **c) for i, c in self._closing.items()]
        raise AssertionError(f"unexpected path {path}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()
    instruments = [
        {"instrumentId": 1001, "symbol": "AAPL", "displayName": "Apple",
         "assetClass": "Stocks", "exchangeName": "Nasdaq", "currentRate": 213.6},
        {"instrumentId": 1002, "symbol": "MSFT", "displayName": "Microsoft",
         "assetClass": "Stocks", "exchangeName": "Nasdaq", "currentRate": 400.0},
        {"instrumentId": 9000, "symbol": "ABT", "displayName": "Arcblock",
         "assetClass": "Crypto", "exchangeName": "Digital Currency", "currentRate": 0.21},
    ]
    rates = {1001: {"bid": 213.5, "ask": 213.7, "lastExecution": 213.6}}  # no MSFT
    closing = {1001: {"officialClosingPrice": 210.0, "isMarketOpen": True},
               1002: {"officialClosingPrice": 396.0, "isMarketOpen": True}}
    fake = FakeEtoro(instruments, rates, closing)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    monkeypatch.setattr(screener, "_load_universe", lambda u: [
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Tech"},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Tech"},
        {"ticker": "ABT", "name": "Abbott Laboratories", "sector": "Health"},
        {"ticker": "NOPE", "name": "Unmapped Co.", "sector": "X"},
    ])
    from main import app
    return TestClient(app), fake


def test_refresh_catalog_populates(client):
    tc, _ = client
    r = tc.post("/screener/refresh-etoro-catalog")
    assert r.status_code == 200
    assert r.json()["instruments"] == 3


def test_screener_live_prices_and_computed_change(client):
    tc, _ = client
    tc.post("/screener/refresh-etoro-catalog")
    rows = {x["ticker"]: x for x in tc.get("/screener/sp500").json()}
    aapl = rows["AAPL"]
    assert aapl["price"] == 213.6 and aapl["sell"] == 213.5 and aapl["buy"] == 213.7
    assert aapl["exchange"] == "Nasdaq" and aapl["instrument_id"] == 1001
    assert aapl["is_open"] is True
    # change% = (213.6 - 210.0)/210.0*100 = 1.714...
    assert round(aapl["change_pct"], 2) == 1.71
    assert aapl["sentiment_buy_pct"] is None  # not exposed by the API
    assert rows["NOPE"]["price"] is None


def test_price_falls_back_to_current_rate(client):
    tc, _ = client
    tc.post("/screener/refresh-etoro-catalog")
    rows = {x["ticker"]: x for x in tc.get("/screener/sp500").json()}
    msft = rows["MSFT"]
    assert msft["price"] == 400.0          # from catalog currentRate (no /rates entry)
    assert msft["sell"] is None and msft["buy"] is None
    assert round(msft["change_pct"], 2) == 1.01   # (400-396)/396*100


def test_refresh_uses_no_fields_param(client):
    """discover must be called WITHOUT a `fields` param (eToro 500s otherwise)."""
    tc, fake = client
    tc.post("/screener/refresh-etoro-catalog")
    discover_calls = [c for c in fake.calls if c[1] == "/api/v1/instruments/discover"]
    assert discover_calls
    for _, _, params in discover_calls:
        assert "fields" not in params


def test_crypto_symbol_collision_treated_as_unmapped(client):
    tc, _ = client
    tc.post("/screener/refresh-etoro-catalog")
    rows = {x["ticker"]: x for x in tc.get("/screener/sp500").json()}
    abt = rows["ABT"]
    # ABT only exists as a Crypto instrument on eToro -> must NOT show crypto data
    assert abt["price"] is None
    assert abt["instrument_id"] is None
    assert abt["exchange"] is None
