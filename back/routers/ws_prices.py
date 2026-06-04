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
