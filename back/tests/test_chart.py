import pytest
from fastapi.testclient import TestClient


class FakeCandleClient:
    def request(self, method, path, params=None, json=None):
        assert "history/candles/desc/OneDay/300" in path
        return {"interval": "OneDay", "candles": [{"instrumentId": 1001, "candles": [
            {"fromDate": "2026-06-05T00:00:00Z", "open": 311.11, "high": 311.68, "low": 310.15, "close": 310.57, "volume": 10115.0},
            {"fromDate": "2026-06-04T00:00:00Z", "open": 311.29, "high": 314.7, "low": 309.66, "close": 311.11, "volume": 36125964.0},
            {"fromDate": "bad-date", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": None},
            {"fromDate": "2026-06-03T00:00:00Z", "open": None, "high": 1.0, "low": 1.0, "close": 1.0, "volume": None},
        ]}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import chart, screener
    from data_cache.etoro_catalog import EtoroCatalog
    db = tmp_path / "cat.db"
    EtoroCatalog(db).upsert([{"symbol": "AAPL", "instrument_id": 1001,
                              "asset_class": "Stocks", "display_name": "Apple"}])
    monkeypatch.setattr(screener, "CATALOG_DB", db)
    monkeypatch.setattr(chart, "get_server_client", lambda: FakeCandleClient())
    from main import app
    return TestClient(app)


def test_chart_normalizes_ascending_epoch_ms_and_enriches(client):
    r = client.get("/charts/1001?interval=OneDay&count=300")
    assert r.status_code == 200
    b = r.json()
    assert b["instrument_id"] == 1001 and b["symbol"] == "AAPL" and b["name"] == "Apple"
    assert b["interval"] == "OneDay"
    assert len(b["candles"]) == 2                              # bad-date + missing-open dropped
    times = [c["time"] for c in b["candles"]]
    assert times == sorted(times)                              # ascending
    assert all(isinstance(t, int) and t > 1_000_000_000_000 for t in times)  # epoch ms
    assert b["candles"][0]["open"] == 311.29 and b["candles"][1]["open"] == 311.11
    assert b["candles"][1]["volume"] == 10115.0
