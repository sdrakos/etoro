from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false")
    from routers.etoro import trading
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(trading.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_demo_open_by_amount_passthrough(client):
    c, fake = client
    body = {"InstrumentID": 100000, "IsBuy": True, "Leverage": 1, "Amount": 100}
    r = c.post("/etoro/trading/execution/demo/market-open-orders/by-amount",
               headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200 and r.json() == {"ok": True}
    method, path = fake.request.call_args.args
    assert method == "POST"
    assert path == "/trading/execution/demo/market-open-orders/by-amount"
    assert fake.request.call_args.kwargs["json"] == body


def test_real_execution_blocked_when_flag_off(client):
    c, fake = client
    r = c.post("/etoro/trading/execution/market-open-orders/by-amount",
               headers={"X-User-Id": "u1"},
               json={"InstrumentID": 1, "IsBuy": True, "Leverage": 1, "Amount": 100})
    assert r.status_code == 403
    assert fake.request.call_count == 0


def test_real_execution_allowed_when_flag_on(client, monkeypatch):
    c, fake = client
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "true")
    r = c.post("/etoro/trading/execution/market-open-orders/by-amount",
               headers={"X-User-Id": "u1"},
               json={"InstrumentID": 1, "IsBuy": True, "Leverage": 1, "Amount": 100})
    assert r.status_code == 200


def test_info_portfolio_passthrough(client):
    c, fake = client
    r = c.get("/etoro/trading/info/demo/portfolio", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/trading/info/demo/portfolio"
