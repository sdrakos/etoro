from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routers.etoro import market_data
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(market_data.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_search_passthrough(client):
    c, fake = client
    r = c.get("/etoro/market-data/search",
              params={"fields": "instrumentId,displayname", "searchText": "BTC"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/market-data/search"
    assert fake.request.call_args.kwargs["params"] == {
        "fields": "instrumentId,displayname", "searchText": "BTC"}


def test_candles_passthrough_builds_path(client):
    c, fake = client
    r = c.get("/etoro/market-data/instruments/100000/history/candles/desc/OneDay/50")
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/market-data/instruments/100000/history/candles/desc/OneDay/50"
