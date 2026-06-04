"""WebSocket price relay: one shared upstream eToro feed, fanned out to browsers."""
from __future__ import annotations
import asyncio
from collections import Counter
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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

    async def start(self) -> None:
        await self._client.start()

    async def stop(self) -> None:
        for t in list(self._pending.values()):
            t.cancel()
        self._pending.clear()
        await self._client.stop()

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
            try:
                await self._send(browser, tick)
            except Exception:
                await self.detach(browser)  # drop a dead client; never break fan-out to others

    async def _send(self, browser, tick: Tick) -> None:
        await browser.send_json({
            "instrumentId": tick.instrument_id,
            "bid": tick.bid, "ask": tick.ask, "last": tick.last,
            "change_pct": compute_change(tick.last, self._prev_close.get(tick.instrument_id)),
            "ts": tick.ts,
        })


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


_start_task = None


def _ensure_started() -> None:
    """Lazily start the upstream connection on the first browser subscriber.

    Single-threaded event loop: the check/set below does no `await`, so concurrent
    first-connections in the same tick can't race. Do not insert an `await` here.
    """
    global _started, _start_task
    if not _started:
        _started = True
        _start_task = asyncio.create_task(get_relay().start())


async def stop_relay() -> None:
    global _relay, _started, _start_task
    if _relay is not None:
        await _relay.stop()
    _relay, _started, _start_task = None, False, None


@router.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    await ws.accept()
    try:
        relay = get_relay()
    except Exception:
        await ws.close(code=1011)  # keys missing / relay unavailable
        return
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
