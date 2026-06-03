from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routers.etoro import social
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(social.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_list_watchlists_passthrough(client):
    c, fake = client
    r = c.get("/etoro/watchlists", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/watchlists"


def test_create_watchlist_uses_query_params(client):
    c, fake = client
    r = c.post("/etoro/watchlists", headers={"X-User-Id": "u1"},
               params={"name": "Tech"})
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/watchlists"
    assert fake.request.call_args.kwargs["params"] == {"name": "Tech"}


def test_post_feed_passthrough(client):
    c, fake = client
    r = c.post("/etoro/feeds/post", headers={"X-User-Id": "u1"},
               json={"message": "hi"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "POST" and path == "/feeds/post"
