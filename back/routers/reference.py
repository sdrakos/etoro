from fastapi import APIRouter, Depends
from typing import Optional

from config import get_client
from utils import safe_call, take, to_dict

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/exchanges")
def exchanges(asset_class: Optional[str] = None, locale: Optional[str] = None,
              client=Depends(get_client)):
    return to_dict(safe_call(client.get_exchanges, asset_class=asset_class, locale=locale))


@router.get("/market-status")
def market_status(client=Depends(get_client)):
    return to_dict(safe_call(client.get_market_status))


@router.get("/market-holidays")
def market_holidays(client=Depends(get_client)):
    return to_dict(safe_call(client.get_market_holidays))


@router.get("/conditions")
def conditions(
    asset_class: Optional[str] = None,
    data_type: Optional[str] = None,
    sip: Optional[str] = None,
    limit: int = 250,
    client=Depends(get_client),
):
    params = {k: v for k, v in {
        "asset_class": asset_class, "data_type": data_type, "sip": sip,
    }.items() if v}
    it = safe_call(client.list_conditions, **params, limit=1000)
    return take(it, limit)
