from unittest.mock import patch
import pytest
from fastapi import HTTPException


def test_uses_vault_credentials_when_present(monkeypatch):
    import etoro_api.deps as deps
    from etoro_api.vault import Credentials
    monkeypatch.setattr(deps.vault, "get_credentials",
                        lambda uid: Credentials("PUB", "USR", "demo"))
    client = deps.get_etoro_client(x_user_id="u1")
    assert client.public_key == "PUB"
    assert client.user_key == "USR"


def test_falls_back_to_env_when_no_row(monkeypatch):
    import etoro_api.deps as deps
    monkeypatch.setattr(deps.vault, "get_credentials", lambda uid: None)
    monkeypatch.setenv("ETORO_PUBLIC_KEY", "ENVPUB")
    monkeypatch.setenv("ETORO_PRIVATE_KEY", "ENVUSR")
    client = deps.get_etoro_client(x_user_id="u1")
    assert client.public_key == "ENVPUB"
    assert client.user_key == "ENVUSR"


def test_raises_when_no_creds_anywhere(monkeypatch):
    import etoro_api.deps as deps
    monkeypatch.setattr(deps.vault, "get_credentials", lambda uid: None)
    monkeypatch.delenv("ETORO_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ETORO_PRIVATE_KEY", raising=False)
    with pytest.raises(HTTPException) as ei:
        deps.get_etoro_client(x_user_id="u1")
    assert ei.value.status_code == 400
