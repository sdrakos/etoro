"""eToro candlestick data for the chart view (server client, demo)."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from etoro_api.server import get_server_client
from data_cache.etoro_catalog import EtoroCatalog

router = APIRouter(prefix="/charts", tags=["charts"])


class Candle(BaseModel):
    time: int          # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class ChartResponse(BaseModel):
    instrument_id: int
    symbol: Optional[str] = None
    name: Optional[str] = None
    interval: str
    candles: list[Candle]


def _epoch_ms(iso) -> Optional[int]:
    if not isinstance(iso, str):
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


@router.get("/{instrument_id}", response_model=ChartResponse)
def chart(instrument_id: int, interval: str = Query("OneDay"),
          count: int = Query(300), account: str = Query("demo")):
    count = max(1, min(count, 1000))
    client = get_server_client()
    raw = client.request(
        "GET",
        f"/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/{interval}/{count}")
    groups = (raw or {}).get("candles") or []
    inner = (groups[0].get("candles") if groups else []) or []

    out: list[Candle] = []
    for c in inner:
        t = _epoch_ms(c.get("fromDate"))
        o, h, l, cl = c.get("open"), c.get("high"), c.get("low"), c.get("close")
        if t is None or None in (o, h, l, cl):
            continue
        out.append(Candle(time=t, open=o, high=h, low=l, close=cl, volume=c.get("volume")))
    out.sort(key=lambda x: x.time)

    from routers import screener  # late import: lets tests monkeypatch screener.CATALOG_DB
    meta = (EtoroCatalog(screener.CATALOG_DB)
            .get_by_instrument_ids([instrument_id]).get(instrument_id, {}))
    return ChartResponse(instrument_id=instrument_id, symbol=meta.get("symbol"),
                         name=meta.get("display_name"), interval=interval, candles=out)
