from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routers.etoro import agent_portfolios
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(agent_portfolios.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_list_sub_portfolios(client):
    c, fake = client
    r = c.get("/etoro/sub-portfolios", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/sub-portfolios"


def test_create_sub_portfolio_passthrough_body(client):
    c, fake = client
    body = {"investmentAmountInUsd": 2000, "subPortfolioName": "alpha1",
            "userTokenName": "tok", "scopeIds": [201]}
    r = c.post("/etoro/sub-portfolios", headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200
    assert fake.request.call_args.kwargs["json"] == body
