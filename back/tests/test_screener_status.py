import time
from fastapi.testclient import TestClient


def test_refresh_once_sets_timestamp(monkeypatch):
    from routers import screener
    monkeypatch.setattr(screener, "refresh_catalog", lambda: {"instruments": 7})
    screener._last_refresh_ts = None
    result = screener._refresh_once()
    assert result == {"instruments": 7}
    assert screener._last_refresh_ts is not None


def test_catalog_status_endpoint(tmp_path, monkeypatch):
    from routers import screener
    from data_cache.etoro_catalog import EtoroCatalog
    db = tmp_path / "cat.db"
    EtoroCatalog(db).upsert([{"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks"}])
    monkeypatch.setattr(screener, "CATALOG_DB", db)
    screener._last_refresh_ts = time.time() - 5
    from main import app
    tc = TestClient(app)
    r = tc.get("/screener/catalog-status")
    assert r.status_code == 200
    body = r.json()
    assert body["instruments"] == 1
    assert 4 <= body["last_refresh_age_s"] <= 30
