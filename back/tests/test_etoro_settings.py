from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from routers.etoro import settings
    store = {}
    monkeypatch.setattr(settings.vault, "set_credentials",
                        lambda uid, pub, usr, env: store.update(
                            user_id=uid, public=pub, user=usr, env=env))
    monkeypatch.setattr(settings.vault, "get_credentials",
                        lambda uid: MagicMock(environment="demo", public_key="ABCD1234"))
    monkeypatch.setattr(settings.vault, "delete_credentials",
                        lambda uid: store.clear())
    app = FastAPI()
    app.include_router(settings.router)
    return TestClient(app), store


def test_post_credentials_stores(client):
    c, store = client
    r = c.post("/etoro/credentials",
               headers={"X-User-Id": "u1"},
               json={"public_key": "P", "user_key": "U", "environment": "demo"})
    assert r.status_code == 200
    assert store["public"] == "P" and store["env"] == "demo"


def test_get_status_masks_key(client):
    c, _ = client
    r = c.get("/etoro/credentials", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    body = r.json()
    assert body["has_keys"] is True
    assert body["public_key_last4"] == "1234"


def test_post_rejects_bad_environment(client):
    c, _ = client
    r = c.post("/etoro/credentials", headers={"X-User-Id": "u1"},
               json={"public_key": "P", "user_key": "U", "environment": "paper"})
    assert r.status_code == 422
