"""eToro trading endpoints: execution (demo + real) and portfolio/PnL info.

Real-money execution (paths without /demo/) is gated behind the
QUANTIQ_ALLOW_REAL_EXECUTION env flag (default off -> 403).
"""
import os
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro/trading", tags=["etoro:trading"])


def _guard_real() -> None:
    if os.getenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false").lower() not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=403,
            detail="real-money execution disabled. Set QUANTIQ_ALLOW_REAL_EXECUTION=true to enable.")


# ---------------- Demo execution ----------------

@router.post("/execution/demo/market-open-orders/by-amount")
def demo_open_by_amount(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/trading/execution/demo/market-open-orders/by-amount", json=body)


@router.post("/execution/demo/market-open-orders/by-units")
def demo_open_by_units(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/trading/execution/demo/market-open-orders/by-units", json=body)


@router.delete("/execution/demo/market-open-orders/{order_id}")
def demo_cancel_open(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/trading/execution/demo/market-open-orders/{order_id}")


@router.post("/execution/demo/market-close-orders/positions/{position_id}")
def demo_close_position(position_id: str, body: dict = Body(...),
                        client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", f"/trading/execution/demo/market-close-orders/positions/{position_id}", json=body)


@router.delete("/execution/demo/market-close-orders/{order_id}")
def demo_cancel_close(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/trading/execution/demo/market-close-orders/{order_id}")


@router.post("/execution/demo/limit-orders")
def demo_limit_open(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/trading/execution/demo/limit-orders", json=body)


@router.delete("/execution/demo/limit-orders/{order_id}")
def demo_limit_cancel(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/trading/execution/demo/limit-orders/{order_id}")


# ---------------- Real execution (guarded) ----------------

@router.post("/execution/market-open-orders/by-amount")
def real_open_by_amount(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", "/trading/execution/market-open-orders/by-amount", json=body)


@router.post("/execution/market-open-orders/by-units")
def real_open_by_units(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", "/trading/execution/market-open-orders/by-units", json=body)


@router.delete("/execution/market-open-orders/{order_id}")
def real_cancel_open(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("DELETE", f"/trading/execution/market-open-orders/{order_id}")


@router.post("/execution/market-close-orders/positions/{position_id}")
def real_close_position(position_id: str, body: dict = Body(...),
                        client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", f"/trading/execution/market-close-orders/positions/{position_id}", json=body)


@router.delete("/execution/market-close-orders/{order_id}")
def real_cancel_close(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("DELETE", f"/trading/execution/market-close-orders/{order_id}")


@router.post("/execution/limit-orders")
def real_limit_open(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", "/trading/execution/limit-orders", json=body)


@router.delete("/execution/limit-orders/{order_id}")
def real_limit_cancel(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("DELETE", f"/trading/execution/limit-orders/{order_id}")


# ---------------- Info & portfolio ----------------

@router.get("/info/demo/pnl")
def demo_pnl(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/demo/pnl")


@router.get("/info/real/pnl")
def real_pnl(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/real/pnl")


@router.get("/info/demo/portfolio")
def demo_portfolio(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/demo/portfolio")


@router.get("/info/portfolio")
def real_portfolio(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/portfolio")


@router.get("/info/trade/history")
def trade_history(minDate: str, page: Optional[int] = None, pageSize: Optional[int] = None,
                  client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/trade/history", params=drop_none({
        "minDate": minDate, "page": page, "pageSize": pageSize}))
