# Screener live prices via WebSocket — Implementation Plan (Spec 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the screener's 30s price polling with a true tick-by-tick eToro WebSocket feed (live bid/ask/last + correct live change%), via a backend relay that holds one shared upstream connection and fans out to browsers.

**Architecture:** A single backend `EtoroWsClient` holds one authenticated `wss://ws.etoro.com/ws` connection (app keys). A `PriceRelay` ref-counts instrument subscriptions across all browser clients, computes live change% from cached prevClose, and fans out ticks over a FastAPI `/ws/prices` endpoint. The React screener fetches the row list via REST (seed) and overlays live ticks from a `usePriceStream` hook.

**Tech Stack:** Backend: FastAPI WebSocket, `websockets` (already installed, 15.0.1), asyncio, pytest (async tests via `asyncio.run`, no new deps). Frontend: native `WebSocket`, React hook, Vitest.

Backend commands from `etoro/back/`; frontend from `etoro/front/`. Clean commits, **no** Co-Authored-By trailer. Repo branch: `feat/yahoo-data-source` (synced to `main` after each task by the controller).

**Design source:** `docs/superpowers/specs/2026-06-04-screener-websocket-live-design.md`.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/etoro_api/ws_client.py` | `Tick`, message builders, `parse_messages`, `EtoroWsClient` (one upstream connection, auth/sub/unsub/reconnect, async tick callback) |
| `back/routers/ws_prices.py` | `compute_change`, `PriceRelay` (ref-count + debounced unsub + fan-out), `/ws/prices` endpoint, lazy singleton |
| `back/main.py` | include the ws router; stop the relay on shutdown |
| `back/tests/test_etoro_ws_client.py` | builders + parse + `_serve` loop with a fake socket |
| `back/tests/test_price_relay.py` | ref-count/diff/debounce/fan-out/change% with a fake client |
| `back/tests/test_ws_prices_endpoint.py` | FastAPI `TestClient` websocket round-trip (snapshot) |
| `front/vite.config.ts` | add `/ws` proxy (`ws: true`) |
| `front/src/hooks/usePriceStream.ts` | browser WS client: reconnect, `Map<id,LiveTick>`, `subscribe(ids)`, `status` |
| `front/src/components/ScreenerTable.tsx` | overlay live ticks over seed rows (flash highlight) |
| `front/src/App.tsx` | subscribe page ids; relax the 30s poll; stream status indicator |
| `front/src/__tests__/usePriceStream.test.ts` | mock WebSocket → tick map + resend on reconnect |
| `front/src/__tests__/ScreenerTable.test.tsx` | overlay assertion (extend existing) |

**Mapping note (eToro semantics):** in the table, **Sell = bid**, **Buy = ask**. The relay emits `bid/ask/last/change_pct`; the table overlays `sell←bid`, `buy←ask`, `price←last`.

---

### Task 1: `Tick` + message builders + `parse_messages` (pure, in `ws_client.py`)

**Files:**
- Create: `back/etoro_api/ws_client.py`
- Test: `back/tests/test_etoro_ws_client.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_ws_client.py
import json
from etoro_api.ws_client import Tick, build_auth, build_subscribe, build_unsubscribe, parse_messages


def test_build_auth_shape():
    msg = build_auth("APIKEY", "USERKEY")
    assert msg["operation"] == "Authenticate"
    assert msg["data"] == {"userKey": "USERKEY", "apiKey": "APIKEY"}
    assert isinstance(msg["id"], str) and msg["id"]


def test_build_subscribe_topics_sorted_with_snapshot():
    msg = build_subscribe({100000, 1001})
    assert msg["operation"] == "Subscribe"
    assert msg["data"]["topics"] == ["instrument:1001", "instrument:100000"]
    assert msg["data"]["snapshot"] is True


def test_build_unsubscribe_no_snapshot():
    msg = build_unsubscribe({1001})
    assert msg["operation"] == "Unsubscribe"
    assert msg["data"]["topics"] == ["instrument:1001"]
    assert "snapshot" not in msg["data"]


def test_parse_messages_extracts_ticks():
    raw = {"messages": [
        {"topic": "instrument:100000", "type": "Trading.Instrument.Rate",
         "content": json.dumps({"Bid": 64990.0, "Ask": 65010.0, "LastExecution": 65000.0,
                                "Date": "2026-06-04T10:00:00Z"})},
        {"topic": "instrument:1", "type": "SomethingElse", "content": "{}"},  # ignored type
    ]}
    ticks = parse_messages(raw)
    assert len(ticks) == 1
    t = ticks[0]
    assert (t.instrument_id, t.bid, t.ask, t.last, t.ts) == (
        100000, 64990.0, 65010.0, 65000.0, "2026-06-04T10:00:00Z")


def test_parse_messages_skips_bad_content_and_empty():
    assert parse_messages({}) == []
    bad = {"messages": [{"topic": "instrument:5", "type": "Trading.Instrument.Rate",
                         "content": "not-json"}]}
    assert parse_messages(bad) == []
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_etoro_ws_client.py -v`
Expected: FAIL — `etoro_api.ws_client` does not exist.

- [ ] **Step 3: Create `back/etoro_api/ws_client.py` (pure parts only)**

```python
"""Single shared upstream eToro WebSocket client (market-data fan-out)."""
from __future__ import annotations
import asyncio
import inspect
import json
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import websockets

WS_URL = "wss://ws.etoro.com/ws"
# Same Cloudflare-friendly UA as the REST client (etoro_api/client.py).
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QUANTIQ/1.0"


@dataclass
class Tick:
    instrument_id: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    ts: Optional[str] = None


def build_auth(api_key: str, user_key: str) -> dict:
    return {"id": str(uuid.uuid4()), "operation": "Authenticate",
            "data": {"userKey": user_key, "apiKey": api_key}}


def build_subscribe(ids, snapshot: bool = True) -> dict:
    return {"id": str(uuid.uuid4()), "operation": "Subscribe",
            "data": {"topics": [f"instrument:{i}" for i in sorted(ids)], "snapshot": snapshot}}


def build_unsubscribe(ids) -> dict:
    return {"id": str(uuid.uuid4()), "operation": "Unsubscribe",
            "data": {"topics": [f"instrument:{i}" for i in sorted(ids)]}}


def parse_messages(raw: dict) -> list[Tick]:
    out: list[Tick] = []
    for m in (raw.get("messages") or []):
        if m.get("type") != "Trading.Instrument.Rate":
            continue
        topic = m.get("topic", "")
        if not topic.startswith("instrument:"):
            continue
        try:
            iid = int(topic.split(":", 1)[1])
        except (ValueError, IndexError):
            continue
        content = m.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        if not isinstance(content, dict):
            continue
        out.append(Tick(instrument_id=iid, bid=content.get("Bid"), ask=content.get("Ask"),
                        last=content.get("LastExecution"), ts=content.get("Date")))
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_etoro_ws_client.py -v` → PASS (5).

- [ ] **Step 5: Commit**

```bash
git add back/etoro_api/ws_client.py back/tests/test_etoro_ws_client.py
git commit -m "feat(etoro-ws): Tick + message builders + parse_messages"
```

---

### Task 2: `EtoroWsClient` connection loop (auth → subscribe → ticks → reconnect)

**Files:**
- Modify: `back/etoro_api/ws_client.py`
- Test: `back/tests/test_etoro_ws_client.py`

- [ ] **Step 1: Add the failing test**

Append to `back/tests/test_etoro_ws_client.py`:
```python
import asyncio
from etoro_api.ws_client import EtoroWsClient


class FakeWS:
    """In-memory websocket: records sent frames, yields canned incoming frames once."""
    def __init__(self, incoming):
        self.sent = []
        self._incoming = [json.dumps(x) for x in incoming]
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._incoming:
            return self._incoming.pop(0)
        raise StopAsyncIteration


def test_serve_authenticates_then_subscribes_active_then_emits_ticks():
    captured: list = []
    tick_frame = {"messages": [{"topic": "instrument:100000", "type": "Trading.Instrument.Rate",
                                "content": json.dumps({"Bid": 1.0, "Ask": 2.0, "LastExecution": 1.5,
                                                       "Date": "T"})}]}
    ws = FakeWS([tick_frame])
    client = EtoroWsClient("API", "USER")
    client._active = {100000}                      # pretend already subscribed
    client.on_tick(lambda t: captured.append(t))

    asyncio.run(client._serve(ws))

    assert ws.sent[0]["operation"] == "Authenticate"
    assert ws.sent[1]["operation"] == "Subscribe"
    assert ws.sent[1]["data"]["topics"] == ["instrument:100000"]
    assert len(captured) == 1 and captured[0].instrument_id == 100000
    assert client.last(100000).bid == 1.0


def test_subscribe_tracks_active_and_sends_when_connected():
    ws = FakeWS([])
    client = EtoroWsClient("API", "USER")
    client._ws = ws
    asyncio.run(client.subscribe({1001, 1002}))
    assert client._active == {1001, 1002}
    assert ws.sent[-1]["operation"] == "Subscribe"
    # subscribing the same ids again sends nothing new
    ws.sent.clear()
    asyncio.run(client.subscribe({1001}))
    assert ws.sent == []
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_etoro_ws_client.py -v`
Expected: FAIL — `EtoroWsClient` not defined.

- [ ] **Step 3: Append `EtoroWsClient` to `back/etoro_api/ws_client.py`**

```python
class EtoroWsClient:
    """One upstream eToro WS connection. Reconnects, re-subscribes, fans out ticks.

    `connect` is injectable for tests. `on_tick(cb)` may take a sync OR async callback.
    """
    def __init__(self, api_key: str, user_key: str, *, url: str = WS_URL, connect=None):
        self._api_key = api_key
        self._user_key = user_key
        self._url = url
        self._connect = connect or self._default_connect
        self._ws = None
        self._active: set[int] = set()
        self._last: dict[int, Tick] = {}
        self._cb: Optional[Callable] = None
        self._task: Optional[asyncio.Task] = None
        self._stopped = False

    def on_tick(self, cb: Callable) -> None:
        self._cb = cb

    def last(self, instrument_id: int) -> Optional[Tick]:
        return self._last.get(int(instrument_id))

    async def _default_connect(self):
        return await websockets.connect(self._url, additional_headers={
            "User-Agent": _USER_AGENT, "x-api-key": self._api_key, "x-user-key": self._user_key})

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopped = False
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopped = True
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._task is not None:
            self._task.cancel()

    async def subscribe(self, ids) -> None:
        ids = {int(i) for i in ids} - self._active
        if not ids:
            return
        self._active |= ids
        if self._ws is not None:
            await self._ws.send(json.dumps(build_subscribe(ids)))

    async def unsubscribe(self, ids) -> None:
        ids = {int(i) for i in ids} & self._active
        if not ids:
            return
        self._active -= ids
        if self._ws is not None:
            await self._ws.send(json.dumps(build_unsubscribe(ids)))

    async def _emit(self, tick: Tick) -> None:
        self._last[tick.instrument_id] = tick
        if self._cb is None:
            return
        res = self._cb(tick)
        if inspect.isawaitable(res):
            await res

    async def _serve(self, ws) -> None:
        """Authenticate, (re)subscribe the active set, then pump ticks until the socket ends."""
        self._ws = ws
        await ws.send(json.dumps(build_auth(self._api_key, self._user_key)))
        if self._active:
            await ws.send(json.dumps(build_subscribe(self._active)))
        async for raw in ws:
            try:
                data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
            except json.JSONDecodeError:
                continue
            for tick in parse_messages(data):
                await self._emit(tick)

    async def _run(self) -> None:
        backoff = 1
        while not self._stopped:
            try:
                ws = await self._connect()
                await self._serve(ws)
                backoff = 1
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            finally:
                self._ws = None
            if self._stopped:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
```

- [ ] **Step 4: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_etoro_ws_client.py -v` → PASS (7).

- [ ] **Step 5: Commit**

```bash
git add back/etoro_api/ws_client.py back/tests/test_etoro_ws_client.py
git commit -m "feat(etoro-ws): EtoroWsClient connect/auth/subscribe/reconnect loop"
```

---

### Task 3: `PriceRelay` — ref-count, debounced unsub, fan-out, live change%

**Files:**
- Create: `back/routers/ws_prices.py`
- Test: `back/tests/test_price_relay.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_price_relay.py
import asyncio
from etoro_api.ws_client import Tick
from routers.ws_prices import PriceRelay, compute_change


class FakeClient:
    """Stands in for EtoroWsClient: records sub/unsub, stores last, holds the tick cb."""
    def __init__(self):
        self.subbed, self.unsubbed = [], []
        self._cb = None
        self._last = {}
    def on_tick(self, cb): self._cb = cb
    def last(self, i): return self._last.get(int(i))
    async def subscribe(self, ids): self.subbed.append(set(ids))
    async def unsubscribe(self, ids): self.unsubbed.append(set(ids))
    async def emit(self, tick):
        self._last[tick.instrument_id] = tick
        r = self._cb(tick)
        if asyncio.iscoroutine(r): await r


class FakeBrowser:
    def __init__(self): self.sent = []
    async def send_json(self, obj): self.sent.append(obj)


def test_compute_change_and_absurd_guard():
    assert compute_change(110.0, 100.0) == 10.0
    assert compute_change(100.0, 100.0) == 0.0
    assert compute_change(100.0, None) is None
    assert compute_change(100.0, 0) is None
    assert compute_change(1000.0, 0.0001) is None   # absurd → None


def test_two_clients_overlapping_ids_subscribe_once_and_fanout():
    async def scenario():
        client = FakeClient()
        relay = PriceRelay(client, prev_close={100000: 100.0})
        a, b = FakeBrowser(), FakeBrowser()
        await relay.set_ids(a, {100000})
        await relay.set_ids(b, {100000})            # overlap → no second upstream subscribe
        assert client.subbed == [{100000}]
        await client.emit(Tick(100000, bid=1.0, ask=2.0, last=110.0, ts="T"))
        # fan-out to BOTH, with change% from prev_close
        assert a.sent[-1] == {"instrumentId": 100000, "bid": 1.0, "ask": 2.0,
                              "last": 110.0, "change_pct": 10.0, "ts": "T"}
        assert b.sent[-1]["instrumentId"] == 100000
    asyncio.run(scenario())


def test_refcount_zero_triggers_debounced_unsubscribe():
    import routers.ws_prices as mod
    async def scenario():
        client = FakeClient()
        relay = PriceRelay(client, prev_close={})
        a = FakeBrowser()
        await relay.set_ids(a, {7})
        assert client.subbed == [{7}]
        await relay.detach(a)                        # refcount 7 → 0
        await asyncio.sleep(0.05)                     # let the (tiny) debounce fire
        assert client.unsubbed == [{7}]
    mod.UNSUB_DEBOUNCE_S = 0.01                       # shrink debounce for the test
    asyncio.run(scenario())


def test_snapshot_sent_to_new_subscriber():
    async def scenario():
        client = FakeClient()
        client._last[100000] = Tick(100000, bid=5.0, ask=6.0, last=5.5, ts="T0")
        relay = PriceRelay(client, prev_close={100000: 5.0})
        a = FakeBrowser()
        await relay.set_ids(a, {100000})
        assert a.sent and a.sent[-1]["bid"] == 5.0    # immediate snapshot
    asyncio.run(scenario())
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_price_relay.py -v`
Expected: FAIL — `routers.ws_prices` does not exist.

- [ ] **Step 3: Create `back/routers/ws_prices.py` (relay only — endpoint added in Task 4)**

```python
"""WebSocket price relay: one shared upstream eToro feed, fanned out to browsers."""
from __future__ import annotations
import asyncio
from collections import Counter
from typing import Optional

from etoro_api.ws_client import EtoroWsClient, Tick

UNSUB_DEBOUNCE_S = 10.0          # keep an upstream sub alive briefly after refcount hits 0
ABSURD_CHANGE = 100.0           # |change%| above this means a bad prevClose → emit None


def compute_change(last: Optional[float], prev_close: Optional[float]) -> Optional[float]:
    if last is None or prev_close in (None, 0):
        return None
    pct = (last - prev_close) / prev_close * 100
    if abs(pct) > ABSURD_CHANGE:
        return None
    return pct


class PriceRelay:
    """Ref-counts instrument subscriptions across browser clients; fans out ticks."""

    def __init__(self, client: EtoroWsClient, prev_close: Optional[dict[int, float]] = None):
        self._client = client
        self._prev_close = dict(prev_close or {})
        self._refcount: Counter[int] = Counter()
        self._subs: dict[int, set] = {}            # instrument_id -> set[browser]
        self._owned: dict[int, set[int]] = {}      # id(browser) -> ids it wants
        self._pending: dict[int, asyncio.Task] = {}  # instrument_id -> debounced unsub task
        client.on_tick(self._on_tick)

    def set_prev_close(self, mapping: dict[int, float]) -> None:
        self._prev_close = dict(mapping)

    async def set_ids(self, browser, ids) -> None:
        ids = {int(i) for i in ids}
        prev = self._owned.get(id(browser), set())
        self._owned[id(browser)] = ids
        for i in ids - prev:
            self._subs.setdefault(i, set()).add(browser)
            self._refcount[i] += 1
            if self._refcount[i] == 1:
                self._cancel_pending(i)
                await self._client.subscribe({i})
            snap = self._client.last(i)
            if snap is not None:
                await self._send(browser, snap)
        for i in prev - ids:
            await self._drop(browser, i)

    async def detach(self, browser) -> None:
        for i in list(self._owned.get(id(browser), set())):
            await self._drop(browser, i)
        self._owned.pop(id(browser), None)

    async def _drop(self, browser, i: int) -> None:
        self._subs.get(i, set()).discard(browser)
        if self._refcount[i] > 0:
            self._refcount[i] -= 1
        if self._refcount[i] == 0:
            self._schedule_unsub(i)

    def _schedule_unsub(self, i: int) -> None:
        self._cancel_pending(i)

        async def _later():
            try:
                await asyncio.sleep(UNSUB_DEBOUNCE_S)
                if self._refcount[i] == 0:
                    await self._client.unsubscribe({i})
            finally:
                self._pending.pop(i, None)

        self._pending[i] = asyncio.create_task(_later())

    def _cancel_pending(self, i: int) -> None:
        t = self._pending.pop(i, None)
        if t is not None:
            t.cancel()

    async def _on_tick(self, tick: Tick) -> None:
        for browser in list(self._subs.get(tick.instrument_id, ())):
            await self._send(browser, tick)

    async def _send(self, browser, tick: Tick) -> None:
        await browser.send_json({
            "instrumentId": tick.instrument_id,
            "bid": tick.bid, "ask": tick.ask, "last": tick.last,
            "change_pct": compute_change(tick.last, self._prev_close.get(tick.instrument_id)),
            "ts": tick.ts,
        })
```

- [ ] **Step 4: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_price_relay.py -v` → PASS (4).

- [ ] **Step 5: Commit**

```bash
git add back/routers/ws_prices.py back/tests/test_price_relay.py
git commit -m "feat(screener-ws): PriceRelay ref-count + fan-out + live change%"
```

---

### Task 4: `/ws/prices` endpoint + lazy singleton + main.py wiring

**Files:**
- Modify: `back/routers/ws_prices.py`, `back/main.py`
- Test: `back/tests/test_ws_prices_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_ws_prices_endpoint.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_ws_prices_endpoint.py -v`
Expected: FAIL — no `/ws/prices` route / no `get_relay`.

- [ ] **Step 3: Append the router + singleton to `back/routers/ws_prices.py`**

Add these imports at the top of the file (next to the existing imports):
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
```
Append at the end of the file:
```python
router = APIRouter(tags=["screener-ws"])

_relay: Optional[PriceRelay] = None
_started = False


def _load_prev_close() -> dict[int, float]:
    """prevClose per instrument for live change%. Best-effort; daily granularity."""
    try:
        from routers.screener import _fetch_closing
        from etoro_api.server import get_server_client
        closing = _fetch_closing(get_server_client())
        return {int(k): v["officialClosingPrice"] for k, v in closing.items()
                if v.get("officialClosingPrice") not in (None, 0)}
    except Exception:
        return {}


def get_relay() -> PriceRelay:
    global _relay
    if _relay is None:
        from etoro_api.server import get_server_client
        c = get_server_client()                       # validates keys (503 if missing)
        client = EtoroWsClient(c.public_key, c.user_key)
        _relay = PriceRelay(client, _load_prev_close())
    return _relay


def _ensure_started() -> None:
    """Lazily start the upstream connection on the first browser subscriber."""
    global _started
    if not _started:
        _started = True
        asyncio.create_task(get_relay()._client.start())


async def stop_relay() -> None:
    global _relay, _started
    if _relay is not None:
        await _relay._client.stop()
    _relay, _started = None, False


@router.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    await ws.accept()
    relay = get_relay()
    _ensure_started()
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("op") == "set":
                await relay.set_ids(ws, {int(x) for x in msg.get("ids", [])})
    except WebSocketDisconnect:
        await relay.detach(ws)
    except Exception:
        await relay.detach(ws)
```
(The FastAPI `WebSocket` already provides `send_json`, so `relay._send`/`_on_tick` work against it directly.)

- [ ] **Step 4: Wire into `back/main.py`**

Add to the routers import block (after `from routers import etoro`):
```python
from routers import ws_prices
```
Register the router (after `app.include_router(etoro.router)`):
```python
app.include_router(ws_prices.router)
```
Stop the relay on shutdown — change the lifespan `finally` block from:
```python
    finally:
        task.cancel()
```
to:
```python
    finally:
        task.cancel()
        await ws_prices.stop_relay()
```

- [ ] **Step 5: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_ws_prices_endpoint.py -v` → PASS (1).
Then full backend suite: `python -m pytest tests/ -q` → all pass.
Then import check: `python -c "import main; print('ok')"` → ok.

- [ ] **Step 6: Commit**

```bash
git add back/routers/ws_prices.py back/main.py back/tests/test_ws_prices_endpoint.py
git commit -m "feat(screener-ws): /ws/prices endpoint + lazy relay singleton + shutdown"
```

---

### Task 5: Frontend `usePriceStream` hook + vite `/ws` proxy

**Files:**
- Modify: `front/vite.config.ts`
- Create: `front/src/hooks/usePriceStream.ts`, `front/src/__tests__/usePriceStream.test.ts`

- [ ] **Step 1: Add the `/ws` proxy in `front/vite.config.ts`**

Change the `proxy` block from:
```typescript
    proxy: {
      "/screener": "http://localhost:8765",
    },
```
to:
```typescript
    proxy: {
      "/screener": "http://localhost:8765",
      "/ws": { target: "ws://localhost:8765", ws: true },
    },
```

- [ ] **Step 2: Write the failing test**

```typescript
// front/src/__tests__/usePriceStream.test.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePriceStream } from "../hooks/usePriceStream";

// Minimal mock WebSocket capturing the latest instance.
class MockWS {
  static last: MockWS | null = null;
  static OPEN = 1;
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { MockWS.last = this; }
  send(d: string) { this.sent.push(d); }
  close() { this.readyState = 3; this.onclose?.(); }
  _open() { this.readyState = 1; this.onopen?.(); }
  _msg(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}

describe("usePriceStream", () => {
  beforeEach(() => {
    MockWS.last = null;
    vi.stubGlobal("WebSocket", MockWS as unknown as typeof WebSocket);
  });

  it("subscribes after open and records ticks", async () => {
    const { result } = renderHook(() => usePriceStream());
    act(() => { result.current.subscribe([100000]); });
    act(() => { MockWS.last!._open(); });            // resends ids on open
    expect(JSON.parse(MockWS.last!.sent.at(-1)!)).toEqual({ op: "set", ids: [100000] });

    act(() => { MockWS.last!._msg({ instrumentId: 100000, bid: 1, ask: 2, last: 1.5, change_pct: 3, ts: "T" }); });
    await waitFor(() => expect(result.current.ticks.get(100000)?.bid).toBe(1));
    expect(result.current.status).toBe("live");
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run (from `front/`): `npm run test:run -- usePriceStream`
Expected: FAIL — module not found.

- [ ] **Step 4: Create `front/src/hooks/usePriceStream.ts`**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";

export interface LiveTick {
  bid: number | null;
  ask: number | null;
  last: number | null;
  change_pct: number | null;
  ts: string | null;
}
export type StreamStatus = "connecting" | "live" | "reconnecting" | "down";

export function usePriceStream() {
  const [ticks, setTicks] = useState<Map<number, LiveTick>>(new Map());
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const idsRef = useRef<number[]>([]);
  const ticksRef = useRef<Map<number, LiveTick>>(new Map());
  const backoffRef = useRef(1000);
  const closedRef = useRef(false);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/prices`);
    wsRef.current = ws;
    ws.onopen = () => {
      setStatus("live");
      backoffRef.current = 1000;
      if (idsRef.current.length) ws.send(JSON.stringify({ op: "set", ids: idsRef.current }));
    };
    ws.onmessage = (e) => {
      let t: any;
      try { t = JSON.parse(e.data); } catch { return; }
      if (t && typeof t.instrumentId === "number") {
        const next = new Map(ticksRef.current);
        next.set(t.instrumentId, { bid: t.bid, ask: t.ask, last: t.last, change_pct: t.change_pct, ts: t.ts });
        ticksRef.current = next;
        setTicks(next);
      }
    };
    ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
    ws.onclose = () => {
      if (closedRef.current) return;
      setStatus("reconnecting");
      window.setTimeout(connect, backoffRef.current);
      backoffRef.current = Math.min(backoffRef.current * 2, 30000);
    };
  }, []);

  useEffect(() => {
    closedRef.current = false;
    connect();
    return () => { closedRef.current = true; wsRef.current?.close(); };
  }, [connect]);

  const subscribe = useCallback((ids: number[]) => {
    idsRef.current = ids;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ op: "set", ids }));
  }, []);

  return { ticks, subscribe, status };
}
```

- [ ] **Step 5: Run to verify it passes**

Run (from `front/`): `npm run test:run -- usePriceStream` → PASS.

- [ ] **Step 6: Commit**

```bash
git add front/vite.config.ts front/src/hooks/usePriceStream.ts front/src/__tests__/usePriceStream.test.ts
git commit -m "feat(front): usePriceStream WS hook + /ws vite proxy"
```

---

### Task 6: Overlay live ticks in `ScreenerTable` + wire `App`

**Files:**
- Modify: `front/src/components/ScreenerTable.tsx`, `front/src/App.tsx`
- Test: `front/src/__tests__/ScreenerTable.test.tsx`

- [ ] **Step 1: Extend `ScreenerTable` test for the overlay**

Replace `front/src/__tests__/ScreenerTable.test.tsx` with:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScreenerTable } from "../components/ScreenerTable";
import type { CategoryRow } from "../types/screener";
import type { LiveTick } from "../hooks/usePriceStream";

const rows: CategoryRow[] = [
  { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
    exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010,
    change_pct: 8.3, sentiment_buy_pct: 90, is_open: true,
    volume: null, market_cap: null, pe_ratio: null },
];

describe("ScreenerTable (eToro columns)", () => {
  it("renders seed values when no ticks", () => {
    render(<ScreenerTable rows={rows} />);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("Bitcoin")).toBeInTheDocument();
    expect(screen.getByText("Digital Currency")).toBeInTheDocument();
    expect(screen.getByText("+8.30%")).toBeInTheDocument();
    expect(screen.getByText("64990.00")).toBeInTheDocument();
    expect(screen.getByText("65010.00")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
  });

  it("overlays a live tick (sell=bid, buy=ask, change)", () => {
    const ticks = new Map<number, LiveTick>([
      [100000, { bid: 70000, ask: 70010, last: 70005, change_pct: -2.5, ts: "T" }],
    ]);
    render(<ScreenerTable rows={rows} ticks={ticks} />);
    expect(screen.getByText("70000.00")).toBeInTheDocument();   // sell ← bid
    expect(screen.getByText("70010.00")).toBeInTheDocument();   // buy ← ask
    expect(screen.getByText("-2.50%")).toBeInTheDocument();     // live change
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- ScreenerTable`
Expected: FAIL — `ScreenerTable` does not accept `ticks` / overlay not applied.

- [ ] **Step 3: Add the `ticks` overlay to `front/src/components/ScreenerTable.tsx`**

Change the imports at the top to also import the tick type:
```tsx
import type { CategoryRow } from "../types/screener";
import type { LiveTick } from "../hooks/usePriceStream";
import { formatPercent, changeColorClass } from "../lib/formatters";
```
Change the `Props` interface and add an effective-row resolver. Replace:
```tsx
interface Props {
  rows: CategoryRow[];
}
```
with:
```tsx
interface Props {
  rows: CategoryRow[];
  ticks?: Map<number, LiveTick>;
}

/** Overlay a live tick onto the REST seed row (Sell←bid, Buy←ask, price←last). */
function withTick(r: CategoryRow, t: LiveTick | undefined): CategoryRow {
  if (!t) return r;
  return {
    ...r,
    sell: t.bid ?? r.sell,
    buy: t.ask ?? r.buy,
    price: t.last ?? r.price,
    change_pct: t.change_pct ?? r.change_pct,
  };
}
```
Change the component signature and the row loop. Replace:
```tsx
export function ScreenerTable({ rows }: Props) {
```
with:
```tsx
export function ScreenerTable({ rows, ticks }: Props) {
```
Then, inside `<tbody>`, change the map header from:
```tsx
          {rows.map((r, i) => {
            const up = (r.change_pct ?? 0) >= 0;
```
to:
```tsx
          {rows.map((seed, i) => {
            const r = withTick(seed, ticks?.get(seed.instrument_id ?? -1));
            const up = (r.change_pct ?? 0) >= 0;
```
(Everything below that uses `r` already, so the live-overlaid row now drives the cells.)

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- ScreenerTable` → PASS (2).

- [ ] **Step 5: Wire `App.tsx` — subscribe page ids, pass ticks, relax poll**

In `front/src/App.tsx`, add the hook import (next to the other hook imports):
```tsx
import { usePriceStream } from "./hooks/usePriceStream";
import { useEffect } from "react";
```
(If `react` is already imported as `import { useCallback, useState } from "react";`, just add `useEffect` to that import instead of a second line.)

Inside `App()`, after the `const status = useQuery(...)` block, add:
```tsx
  const stream = usePriceStream();
  useEffect(() => {
    const ids = (data?.items ?? [])
      .map((r) => r.instrument_id)
      .filter((x): x is number => typeof x === "number");
    if (ids.length) stream.subscribe(ids);
  }, [data, stream]);
```
Relax the category query's poll: in `front/src/hooks/useCategoryData.ts`, change `refetchInterval: 30_000` to `refetchInterval: 300_000` (5 min safety poll; WS now drives price freshness). Keep `staleTime` and `placeholderData` as-is.

Pass ticks to the table — change:
```tsx
          data && <ScreenerTable rows={data.items} />
```
to:
```tsx
          data && <ScreenerTable rows={data.items} ticks={stream.ticks} />
```
Update the header "Live" line to reflect the stream — change the freshness span to prefer the WS status:
```tsx
              <span className="tabular-nums">
                {stream.status === "live" ? "streaming" : freshness(status.data?.last_refresh_age_s)}
              </span>
```

- [ ] **Step 6: Run to verify the suite still passes**

Run (from `front/`): `npm run test:run` → all PASS (App test still green; the MSW handlers don't serve `/ws`, and `usePriceStream` falls back to `connecting`/`reconnecting` harmlessly in jsdom — the App test only asserts tabs + a Bitcoin row, which come from REST/MSW).
If the App test flakes because jsdom has no `WebSocket`, add a one-line guard at the top of `front/src/__tests__/setup.ts`:
```typescript
if (!(globalThis as any).WebSocket) {
  (globalThis as any).WebSocket = class { close() {} send() {} } as unknown as typeof WebSocket;
}
```

- [ ] **Step 7: Commit**

```bash
git add front/src/components/ScreenerTable.tsx front/src/App.tsx front/src/hooks/useCategoryData.ts front/src/__tests__/ScreenerTable.test.tsx front/src/__tests__/setup.ts
git commit -m "feat(front): overlay live WS ticks in screener table + relax poll"
```

---

### Task 7: Full suite + build + e2e + live verify

**Files:**
- Modify: `front/e2e/screener.spec.ts` (only if needed)

- [ ] **Step 1: Backend + frontend test suites + typecheck**

Run (from `back/`): `python -m pytest tests/ -q` → all PASS.
Run (from `front/`): `npm run test:run` → all PASS. Then `npm run build` (`tsc -b && vite build`) → clean, no type errors.

- [ ] **Step 2: Live verify (backend on 8765 + frontend dev)**

Backend (from `back/`): `python -m uvicorn main:app --reload --port 8765`.
Quick protocol check with a tiny WS client (run from `back/`):
```bash
python -c "import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://127.0.0.1:8765/ws/prices') as ws:
        await ws.send(json.dumps({'op':'set','ids':[100000,1001]}))
        for _ in range(3):
            print(await asyncio.wait_for(ws.recv(), timeout=20))
asyncio.run(main())"
```
Expected: JSON frames like `{\"instrumentId\":100000,\"bid\":...,\"ask\":...,\"last\":...,\"change_pct\":...}` (during market hours; for closed markets you may only get the snapshot/last value). If you see frames, the relay→upstream→fan-out path works end-to-end.

Frontend (from `front/`): `npm run dev` → open the URL → the header shows "streaming", Sell/Buy/Change cells **update live** (flash) on open markets; closed markets show the grey dot + last seed price, no ticks. (Skip the GUI step if no display; the WS client check above confirms the backend half.)

- [ ] **Step 3: Update the e2e happy-path if it asserts price staleness**

Read `front/e2e/screener.spec.ts`. The current happy-path asserts tabs/rows/search/pagination — none of which the WS changes — so it should still pass as-is against the WS-enabled UI. Only if an assertion depends on the old "updated Xs ago" header text, relax it to accept "streaming" too. Keep it a happy-path.

- [ ] **Step 4: Commit (if anything changed)**

```bash
git add -A
git commit -m "test(screener-ws): live WS verify + e2e happy-path tweak"
```

---

## Self-Review notes

- **Spec coverage:** `EtoroWsClient` (Tasks 1–2) ↔ spec "Backend — EtoroWsClient"; `PriceRelay` ref-count/debounce/fan-out/change% (Task 3) ↔ "Backend — PriceRelay"; `/ws/prices` + lazy lifespan (Task 4) ↔ "endpoint" + "lifespan"; `usePriceStream` + vite proxy (Task 5) ↔ "Frontend — usePriceStream"; table overlay + App subscribe + relaxed poll + closed-market (Task 6) ↔ "Frontend — App integration" + closed-market handling; tests + e2e + live verify (Task 7) ↔ "Testing". Reconnect/backoff in `EtoroWsClient._run` + `usePriceStream`; absurd-change guard in `compute_change`; snapshot-to-new-subscriber in `PriceRelay.set_ids`. ✓
- **Type/name consistency:** `Tick(instrument_id,bid,ask,last,ts)` defined Task 1, used Tasks 2–3; `EtoroWsClient` methods `start/stop/subscribe/unsubscribe/on_tick/last/_serve/_run` consistent across Tasks 2–4; `PriceRelay(client, prev_close)` + `set_ids/detach` used in Task 4 endpoint; relay tick frame `{instrumentId,bid,ask,last,change_pct,ts}` matches `usePriceStream` parsing (Task 5) and `withTick` overlay (Task 6); `LiveTick` type shared by hook + table. ✓
- **Placeholders:** none. **Deps:** `websockets` already installed (15.0.1); no new frontend deps. **Async tests:** use `asyncio.run(...)` inside sync test fns — no `pytest-asyncio` needed. **Ports:** backend 8765 (vite `/screener` + `/ws` proxy). **Backward-compat:** REST `fetchCategory`/category endpoints untouched; WS only overlays prices; closed markets keep seed price (no fake ticks).
