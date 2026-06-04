"""Portfolio view + live P&L (demo account, app keys) — see WS Spec 2.

Normalizes eToro open positions and enriches them from the instrument catalog
so the frontend can overlay live prices (via /ws/prices) and compute P&L.
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from etoro_api.server import get_server_client
from etoro_api.models import ClosePositionRequest
from routers.etoro.proxy import guard_real
from data_cache.etoro_catalog import EtoroCatalog

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class Position(BaseModel):
    position_id: int
    instrument_id: int
    symbol: Optional[str] = None
    name: Optional[str] = None
    is_buy: bool
    units: float
    open_rate: float
    amount: float
    leverage: float
    current_rate: Optional[float] = None


class PortfolioResponse(BaseModel):
    positions: list[Position]
    account: str


@router.get("/positions", response_model=PortfolioResponse)
def positions(account: str = Query("demo")):
    client = get_server_client()
    seg = "demo/" if account == "demo" else ""
    data = client.request("GET", f"/api/v1/trading/info/{seg}portfolio")
    raw = ((data or {}).get("clientPortfolio") or {}).get("positions") or []

    from routers import screener  # late import: lets tests monkeypatch screener.CATALOG_DB
    cat = EtoroCatalog(screener.CATALOG_DB)
    meta = cat.get_by_instrument_ids(
        [p.get("instrumentID") for p in raw if p.get("instrumentID") is not None])

    out: list[Position] = []
    for p in raw:
        iid = p.get("instrumentID")
        m = meta.get(iid, {})
        out.append(Position(
            position_id=p["positionID"], instrument_id=iid,
            symbol=m.get("symbol"), name=m.get("display_name"),
            is_buy=bool(p.get("isBuy")), units=p.get("units"),
            open_rate=p.get("openRate"), amount=p.get("amount"),
            leverage=p.get("leverage", 1) or 1, current_rate=m.get("current_rate"),
        ))
    return PortfolioResponse(positions=out, account=account)


@router.post("/close/{position_id}")
def close(position_id: int, body: ClosePositionRequest, account: str = Query("demo")):
    if account != "demo":
        guard_real()
    client = get_server_client()
    seg = "demo/" if account == "demo" else ""
    return client.request(
        "POST",
        f"/api/v1/trading/execution/{seg}market-close-orders/positions/{position_id}",
        json=body.model_dump(exclude_none=True))
