from unittest.mock import MagicMock
import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def fake_supabase():
    sb = MagicMock()
    table = sb.table.return_value
    table.upsert.return_value.execute.return_value = MagicMock(data=[{}])
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    return sb


@pytest.fixture
def vault(monkeypatch, fake_supabase):
    monkeypatch.setenv("QUANTIQ_ENC_KEY", Fernet.generate_key().decode())
    import etoro_api.vault as vault
    monkeypatch.setattr(vault, "get_supabase", lambda: fake_supabase)
    return vault


def test_set_credentials_stores_ciphertext_not_plaintext(vault, fake_supabase):
    vault.set_credentials("11111111-1111-1111-1111-111111111111",
                          "PUBKEY", "USERKEY", "demo")
    row = fake_supabase.table.return_value.upsert.call_args.args[0]
    assert row["user_id"] == "11111111-1111-1111-1111-111111111111"
    assert row["environment"] == "demo"
    assert "PUBKEY" not in row["public_key_enc"]
    assert "USERKEY" not in row["user_key_enc"]


def test_get_credentials_roundtrip(vault, fake_supabase):
    f = vault._fernet()
    fake_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{
            "user_id": "u", "environment": "demo",
            "public_key_enc": f.encrypt(b"PUBKEY").decode(),
            "user_key_enc": f.encrypt(b"USERKEY").decode(),
        }]
    )
    creds = vault.get_credentials("u")
    assert creds is not None
    assert creds.public_key == "PUBKEY"
    assert creds.user_key == "USERKEY"
    assert creds.environment == "demo"


def test_get_credentials_missing_returns_none(vault):
    assert vault.get_credentials("nobody") is None
