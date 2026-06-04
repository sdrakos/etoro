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


def _to_float(v) -> Optional[float]:
    """eToro sends rate fields as strings (e.g. \"62908.29\"). Coerce; None on junk."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_messages(raw: dict) -> list[Tick]:
    """Extract price ticks from an eToro WS frame.

    Real rate messages carry only ``topic`` + ``content`` (the documented
    ``type: "Trading.Instrument.Rate"`` is NOT present on the wire), and the
    numeric fields arrive as strings. We accept any ``instrument:<id>`` topic
    whose content has at least one price field, coercing values to float.
    """
    out: list[Tick] = []
    for m in (raw.get("messages") or []):
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
        bid = _to_float(content.get("Bid"))
        ask = _to_float(content.get("Ask"))
        last = _to_float(content.get("LastExecution"))
        if bid is None and ask is None and last is None:
            continue  # not a price message (e.g. an empty/ack payload)
        out.append(Tick(instrument_id=iid, bid=bid, ask=ask, last=last, ts=content.get("Date")))
    return out


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
