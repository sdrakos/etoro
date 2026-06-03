import pytest
from fastapi.testclient import TestClient
from tests.test_screener import FakeEtoro  # reuse the fake


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()
    instruments = [
        {"instrumentId": 1, "symbol": "UP1", "displayname": "Up One",
         "internalExchangeName": "NYSE", "dailyPriceChange": 9.0,
         "buyHoldingPct": 90.0, "isExchangeOpen": True},
        {"instrumentId": 2, "symbol": "UP2", "displayname": "Up Two",
         "internalExchangeName": "NYSE", "dailyPriceChange": 4.0,
         "buyHoldingPct": 60.0, "isExchangeOpen": True},
        {"instrumentId": 3, "symbol": "DN1", "displayname": "Down One",
         "internalExchangeName": "NYSE", "dailyPriceChange": -6.0,
         "buyHoldingPct": 30.0, "isExchangeOpen": True},
    ]
    rates = {i: {"bid": 1.0, "ask": 1.1, "lastExecution": 1.05} for i in (1, 2, 3)}
    fake = FakeEtoro(instruments, rates)
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
    assert rows[0]["change_pct"] == 9.0


def test_movers_losers_sorted_asc(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/movers", params={"direction": "losers", "limit": 1})
    assert r.status_code == 200
    assert r.json()[0]["ticker"] == "DN1"
