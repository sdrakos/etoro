import importlib
import pytest


def test_get_supabase_raises_without_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    import supabase_client
    importlib.reload(supabase_client)
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", None)
    monkeypatch.setattr(supabase_client, "SUPABASE_SERVICE_ROLE_KEY", None)
    supabase_client.get_supabase.cache_clear()
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        supabase_client.get_supabase()


def test_get_supabase_builds_client(monkeypatch):
    import supabase_client
    importlib.reload(supabase_client)
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setattr(supabase_client, "SUPABASE_SERVICE_ROLE_KEY", "svc")
    supabase_client.get_supabase.cache_clear()
    captured = {}
    monkeypatch.setattr(supabase_client, "create_client",
                        lambda url, key: captured.update(url=url, key=key) or "CLIENT")
    assert supabase_client.get_supabase() == "CLIENT"
    assert captured == {"url": "http://localhost:54321", "key": "svc"}
