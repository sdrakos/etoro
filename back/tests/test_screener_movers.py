import pytest
from fastapi.testclient import TestClient
from tests.test_screener import FakeEtoro  # reuse the fake


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()
    instruments = [
        {"instrumentId": 1, "symbol": "UP1", "displayName": "Up One",
         "assetClass": "Stocks", "exchangeName": "NYSE", "currentRate": 11.0},
        {"instrumentId": 2, "symbol": "UP2", "displayName": "Up Two",
         "assetClass": "Stocks", "exchangeName": "NYSE", "currentRate": 10.4},
        {"instrumentId": 3, "symbol": "DN1", "displayName": "Down One",
         "assetClass": "Stocks", "exchangeName": "NYSE", "currentRate": 9.4},
    ]
    rates = {i: {"bid": r-0.05, "ask": r+0.05, "lastExecution": r}
             for i, r in {1: 11.0, 2: 10.4, 3: 9.4}.items()}
    closing = {1: {"officialClosingPrice": 10.0, "isMarketOpen": True},   # +10%
               2: {"officialClosingPrice": 10.0, "isMarketOpen": True},   # +4%
               3: {"officialClosingPrice": 10.0, "isMarketOpen": True}}   # -6%
    fake = FakeEtoro(instruments, rates, closing)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    monkeypatch.setattr(screener, "_load_universe", lambda u: [
        {"ticker": "UP1", "name": "Up One", "sector": "X"},
        {"ticker": "UP2", "name": "Up Two", "sector": "X"},
        {"ticker": "DN1", "name": "Down One", "sector": "X"},
    ])
    from main import app
    return TestClient(app)


def test_movers_gainers_sorted_desc(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/movers", params={"direction": "gainers", "limit": 2})
    assert r.status_code == 200
    rows = r.json()
    assert [x["ticker"] for x in rows] == ["UP1", "UP2"]
    assert rows[0]["change_pct"] == 10.0


def test_movers_losers_sorted_asc(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/movers", params={"direction": "losers", "limit": 1})
    assert r.status_code == 200
    assert r.json()[0]["ticker"] == "DN1"
