from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false")
    from routers.etoro import proxy
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(proxy.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_forwards_v1_path_and_query(client):
    c, fake = client
    r = c.get("/etoro/api/v1/market-data/exchanges", params={"exchangeIds": "4"},
              headers={"X-User-Id": "u1"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/api/v1/market-data/exchanges"
    assert fake.request.call_args.kwargs["params"] == {"exchangeIds": "4"}


def test_forwards_v2_post_body(client):
    c, fake = client
    body = {"action": "open", "transaction": "buy", "instrumentId": 100000, "amount": 100}
    r = c.post("/etoro/api/v2/trading/execution/demo/orders",
               headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "POST" and path == "/api/v2/trading/execution/demo/orders"
    assert fake.request.call_args.kwargs["json"] == body


def test_unknown_version_404(client):
    c, fake = client
    r = c.get("/etoro/api/v3/anything", headers={"X-User-Id": "u1"})
    assert r.status_code == 404
    assert fake.request.call_count == 0


def test_real_execution_blocked_when_flag_off(client):
    c, fake = client
    r = c.post("/etoro/api/v2/trading/execution/orders",  # no /demo/
               headers={"X-User-Id": "u1"}, json={"action": "open"})
    assert r.status_code == 403
    assert fake.request.call_count == 0


def test_demo_execution_allowed_when_flag_off(client):
    c, fake = client
    r = c.post("/etoro/api/v2/trading/execution/demo/orders",
               headers={"X-User-Id": "u1"}, json={"action": "open"})
    assert r.status_code == 200
    assert fake.request.call_count == 1
