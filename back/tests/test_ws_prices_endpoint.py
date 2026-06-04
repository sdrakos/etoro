from fastapi.testclient import TestClient
from etoro_api.ws_client import Tick


def test_ws_prices_snapshot_roundtrip(monkeypatch):
    import routers.ws_prices as mod

    class FakeClient:
        def __init__(self): self._cb = None; self._last = {100000: Tick(100000, 5.0, 6.0, 5.5, "T")}
        def on_tick(self, cb): self._cb = cb
        def last(self, i): return self._last.get(int(i))
        async def subscribe(self, ids): pass
        async def unsubscribe(self, ids): pass
        async def start(self): pass
        async def stop(self): pass

    relay = mod.PriceRelay(FakeClient(), prev_close={100000: 5.0})
    monkeypatch.setattr(mod, "_relay", relay)
    monkeypatch.setattr(mod, "get_relay", lambda: relay)
    monkeypatch.setattr(mod, "_ensure_started", lambda: None)

    from main import app
    with TestClient(app).websocket_connect("/ws/prices") as ws:
        ws.send_json({"op": "set", "ids": [100000]})
        snap = ws.receive_json()
        assert snap["instrumentId"] == 100000
        assert snap["bid"] == 5.0 and snap["change_pct"] == 10.0
