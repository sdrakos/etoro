import pytest
from fastapi import HTTPException


def test_get_server_client_builds_from_env(monkeypatch):
    import etoro_api.server as server
    monkeypatch.setenv("ETORO_PUBLIC_KEY", "PUB")
    monkeypatch.setenv("ETORO_PRIVATE_KEY", "USR")
    client = server.get_server_client()
    assert client.public_key == "PUB"
    assert client.user_key == "USR"


def test_get_server_client_raises_503_without_keys(monkeypatch):
    import etoro_api.server as server
    monkeypatch.delenv("ETORO_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ETORO_PRIVATE_KEY", raising=False)
    with pytest.raises(HTTPException) as ei:
        server.get_server_client()
    assert ei.value.status_code == 503
