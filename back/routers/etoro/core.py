"""Typed convenience endpoints for the common eToro trading actions.

These are friendly, self-documented shortcuts; anything else is reachable via the
generic proxy. `account` selects demo (default) or real; real execution is guarded.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client
from etoro_api.models import UnifiedOrderRequest, ClosePositionRequest
from routers.etoro.proxy import guard_real

router = APIRouter(prefix="/etoro", tags=["etoro:core"])


@router.get("/search")
def search(symbol: str, client: EtoroClient = Depends(get_etoro_client)):
    """Look up an instrument by its exact symbol (e.g. BTC, AAPL, TSLA).

    Uses the Asset Explorer endpoint, which returns the instrument with its
    display name, asset class, exchange, and (for crypto) market data.
    """
    return client.request("GET", f"/api/v1/instruments/{symbol}")


@router.get("/instruments")
def instruments(ids: str, client: EtoroClient = Depends(get_etoro_client)):
    # eToro's instruments endpoint wants repeated params, not a comma list.
    return client.request("GET", "/api/v1/market-data/instruments",
                          params={"instrumentIds": ids.split(",")})


@router.get("/rates")
def rates(ids: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/api/v1/market-data/instruments/rates",
                          params={"instrumentIds": ids.split(",")})


@router.get("/candles/{instrument_id}")
def candles(instrument_id: int, interval: str = "OneDay", count: int = 50,
            direction: str = "desc", client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "GET",
        f"/api/v1/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{count}")


@router.post("/orders")
def create_order(body: UnifiedOrderRequest, account: str = Query("demo"),
                 client: EtoroClient = Depends(get_etoro_client)):
    if account != "demo":
        guard_real()
    seg = "demo/" if account == "demo" else ""
    return client.request("POST", f"/api/v2/trading/execution/{seg}orders",
                          json=body.model_dump(exclude_none=True))


@router.post("/close/{position_id}")
def close_position(position_id: int, body: ClosePositionRequest,
                   account: str = Query("demo"),
                   client: EtoroClient = Depends(get_etoro_client)):
    if account != "demo":
        guard_real()
    seg = "demo/" if account == "demo" else ""
    return client.request(
        "POST",
        f"/api/v1/trading/execution/{seg}market-close-orders/positions/{position_id}",
        json=body.model_dump(exclude_none=True))


@router.get("/portfolio")
def portfolio(account: str = Query("demo"), client: EtoroClient = Depends(get_etoro_client)):
    path = ("/api/v1/trading/info/demo/portfolio" if account == "demo"
            else "/api/v1/trading/info/portfolio")
    return client.request("GET", path)


@router.get("/pnl")
def pnl(account: str = Query("demo"), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/api/v1/trading/info/{account}/pnl")


@router.get("/history")
def history(account: str = Query("demo"), minDate: Optional[str] = None,
            page: Optional[int] = None, pageSize: Optional[int] = None,
            client: EtoroClient = Depends(get_etoro_client)):
    path = ("/api/v1/trading/info/trade/demo/history" if account == "demo"
            else "/api/v1/trading/info/trade/history")
    return client.request("GET", path, params=drop_none({
        "minDate": minDate, "page": page, "pageSize": pageSize}))
