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
