from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def make_client():
    def _make(side_effect=None, return_value=None):
        from routers.etoro import core
        from etoro_api.deps import get_etoro_client
        fake = MagicMock()
        if side_effect is not None:
            fake.request.side_effect = side_effect
        else:
            fake.request.return_value = return_value if return_value is not None else {"ok": True}
        app = FastAPI()
        app.include_router(core.router)
        app.dependency_overrides[get_etoro_client] = lambda: fake
        return TestClient(app), fake
    return _make


def test_search_looks_up_instrument_by_symbol(make_client):
    c, fake = make_client(return_value={
        "instrumentId": 100000, "symbol": "BTC", "displayName": "Bitcoin",
        "assetClass": "Crypto"})
    r = c.get("/etoro/search", params={"symbol": "BTC"}, headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/api/v1/instruments/BTC"
    assert r.json()["displayName"] == "Bitcoin"


def test_instruments_uses_repeated_params(make_client):
    c, fake = make_client(return_value={"instrumentDisplayDatas": []})
    c.get("/etoro/instruments", params={"ids": "100000,100681"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/market-data/instruments"
    assert fake.request.call_args.kwargs["params"] == {"instrumentIds": ["100000", "100681"]}


def test_rates_uses_repeated_params(make_client):
    c, fake = make_client(return_value={"rates": []})
    c.get("/etoro/rates", params={"ids": "100000"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/market-data/instruments/rates"
    assert fake.request.call_args.kwargs["params"] == {"instrumentIds": ["100000"]}


def test_candles_builds_path(make_client):
    c, fake = make_client(return_value={"candles": []})
    r = c.get("/etoro/candles/100000", params={"interval": "OneDay", "count": 30, "direction": "desc"},
              headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/api/v1/market-data/instruments/100000/history/candles/desc/OneDay/30"


def test_create_order_demo_v2_path_and_excludes_none(make_client):
    c, fake = make_client(return_value={"orderId": 1})
    body = {"action": "open", "transaction": "buy", "instrumentId": 100000,
            "amount": 100, "leverage": 1}
    r = c.post("/etoro/orders", params={"account": "demo"}, headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "POST" and path == "/api/v2/trading/execution/demo/orders"
    sent = fake.request.call_args.kwargs["json"]
    assert sent == body and "symbol" not in sent


def test_create_order_real_blocked_when_flag_off(make_client, monkeypatch):
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false")
    c, fake = make_client(return_value={"orderId": 1})
    r = c.post("/etoro/orders", params={"account": "real"}, headers={"X-User-Id": "u1"},
               json={"action": "open", "transaction": "buy", "instrumentId": 1, "amount": 10})
    assert r.status_code == 403
    assert fake.request.call_count == 0


def test_portfolio_and_pnl_paths(make_client):
    c, fake = make_client(return_value={"ok": True})
    c.get("/etoro/portfolio", params={"account": "demo"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/trading/info/demo/portfolio"
    c.get("/etoro/portfolio", params={"account": "real"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/trading/info/portfolio"
    c.get("/etoro/pnl", params={"account": "real"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/trading/info/real/pnl"
