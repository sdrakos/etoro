import pytest
from fastapi.testclient import TestClient


class FakePortfolioClient:
    def __init__(self):
        self.closed = []

    def request(self, method, path, params=None, json=None):
        if method == "GET" and path.endswith("portfolio"):
            return {"clientPortfolio": {"positions": [
                {"positionID": 111, "instrumentID": 1137, "openRate": 215.81,
                 "isBuy": True, "units": 4.633061, "amount": 999.86, "leverage": 1},
                {"positionID": 222, "instrumentID": 99999, "openRate": 10.0,
                 "isBuy": False, "units": 5.0, "amount": 50.0, "leverage": 2},
            ]}}
        if method == "POST" and "market-close-orders" in path:
            self.closed.append((path, json))
            return {"ok": True}
        raise AssertionError(f"unexpected {method} {path}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import portfolio, screener
    from data_cache.etoro_catalog import EtoroCatalog
    db = tmp_path / "cat.db"
    EtoroCatalog(db).upsert([
        {"symbol": "ETH", "instrument_id": 1137, "asset_class": "Crypto",
         "display_name": "Ethereum", "exchange_name": "Digital Currency", "current_rate": 220.0},
    ])
    monkeypatch.setattr(screener, "CATALOG_DB", db)
    fake = FakePortfolioClient()
    monkeypatch.setattr(portfolio, "get_server_client", lambda: fake)
    from main import app
    tc = TestClient(app)
    tc.fake = fake
    return tc


def test_positions_normalizes_and_enriches(client):
    r = client.get("/portfolio/positions")
    assert r.status_code == 200
    body = r.json()
    assert body["account"] == "demo"
    pos = {p["position_id"]: p for p in body["positions"]}
    assert pos[111]["instrument_id"] == 1137
    assert pos[111]["symbol"] == "ETH" and pos[111]["name"] == "Ethereum"
    assert pos[111]["is_buy"] is True and pos[111]["open_rate"] == 215.81
    assert pos[111]["current_rate"] == 220.0
    assert pos[222]["symbol"] is None and pos[222]["is_buy"] is False


def test_close_calls_demo_path_with_body(client):
    r = client.post("/portfolio/close/111", json={"InstrumentID": 1137})
    assert r.status_code == 200 and r.json() == {"ok": True}
    path, payload = client.fake.closed[-1]
    assert "/demo/market-close-orders/positions/111" in path
    assert payload == {"InstrumentID": 1137}
