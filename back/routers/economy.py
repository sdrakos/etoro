from fastapi import APIRouter, Depends
from typing import Optional

from config import get_client
from utils import safe_call, take

router = APIRouter(prefix="/economy", tags=["economy"])


@router.get("/treasury-yields")
def treasury_yields(date_gte: Optional[str] = None, date_lte: Optional[str] = None,
                    limit: int = 250, client=Depends(get_client)):
    params = {k: v for k, v in {"date.gte": date_gte, "date.lte": date_lte}.items() if v}
    it = safe_call(client.list_treasury_yields, **params, limit=1000)
    return take(it, limit)


@router.get("/inflation")
def inflation(date_gte: Optional[str] = None, date_lte: Optional[str] = None,
              limit: int = 100, client=Depends(get_client)):
    params = {k: v for k, v in {"date.gte": date_gte, "date.lte": date_lte}.items() if v}
    it = safe_call(client.list_inflation, **params, limit=1000)
    return take(it, limit)


@router.get("/inflation-expectations")
def inflation_expectations(date_gte: Optional[str] = None, date_lte: Optional[str] = None,
                            limit: int = 100, client=Depends(get_client)):
    params = {k: v for k, v in {"date.gte": date_gte, "date.lte": date_lte}.items() if v}
    it = safe_call(client.list_inflation_expectations, **params, limit=1000)
    return take(it, limit)


@router.get("/fed-funds-rate")
def fed_funds_rate(date_gte: Optional[str] = None, date_lte: Optional[str] = None,
                   limit: int = 250, client=Depends(get_client)):
    params = {k: v for k, v in {"date.gte": date_gte, "date.lte": date_lte}.items() if v}
    it = safe_call(client.list_fed_funds_rate, **params, limit=1000)
    return take(it, limit)
