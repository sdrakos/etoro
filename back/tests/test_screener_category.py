import pytest
from fastapi.testclient import TestClient
from tests.test_screener import FakeEtoro


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()
    instruments = [
        {"instrumentId": 1001, "symbol": "AAPL", "displayName": "Apple",
         "assetClass": "Stocks", "exchangeName": "Nasdaq", "currentRate": 210.0},
        {"instrumentId": 1002, "symbol": "MSFT", "displayName": "Microsoft",
         "assetClass": "Stocks", "exchangeName": "Nasdaq", "currentRate": 400.0},
        {"instrumentId": 100000, "symbol": "BTC", "displayName": "Bitcoin",
         "assetClass": "Crypto", "exchangeName": "Digital Currency", "currentRate": 65000.0},
        {"instrumentId": 9000, "symbol": "ABT", "displayName": "Arcblock",
         "assetClass": "Crypto", "exchangeName": "Digital Currency", "currentRate": 0.2},
    ]
    rates = {100000: {"bid": 64990.0, "ask": 65010.0, "lastExecution": 65000.0}}
    closing = {1001: {"officialClosingPrice": 200.0, "isMarketOpen": True},
               1002: {"officialClosingPrice": 410.0, "isMarketOpen": True},
               100000: {"officialClosingPrice": 60000.0, "isMarketOpen": True},
               9000: {"officialClosingPrice": 0.25, "isMarketOpen": True}}
    fake = FakeEtoro(instruments, rates, closing)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    from main import app
    return TestClient(app)


def test_category_unknown_404(client):
    client.post("/screener/refresh-etoro-catalog")
    assert client.get("/screener/category/widgets").status_code == 404


def test_category_stocks_wrapper_and_filter(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/category/stocks")
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "stocks" and body["total"] == 2
    assert body["page"] == 1 and body["pageSize"] == 50
    assert {x["ticker"] for x in body["items"]} == {"AAPL", "MSFT"}


def test_category_crypto_includes_collision_symbol(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/crypto").json()
    assert {x["ticker"] for x in body["items"]} == {"BTC", "ABT"}
    btc = next(x for x in body["items"] if x["ticker"] == "BTC")
    assert btc["price"] == 65000.0 and btc["sell"] == 64990.0 and btc["buy"] == 65010.0
    assert round(btc["change_pct"], 1) == 8.3


def test_category_sort_change_desc(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/crypto",
                      params={"sort": "change", "dir": "desc"}).json()
    assert [x["ticker"] for x in body["items"]] == ["BTC", "ABT"]


def test_category_text_search(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/stocks", params={"q": "apple"}).json()
    assert body["total"] == 1 and body["items"][0]["ticker"] == "AAPL"


def test_category_pagesize_clamped(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/stocks", params={"pageSize": 9999}).json()
    assert body["pageSize"] == 200
