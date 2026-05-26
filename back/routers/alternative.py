from fastapi import APIRouter, Depends
from typing import Optional

from config import get_client
from utils import safe_call, take

router = APIRouter(prefix="/news", tags=["news"])


@router.get("")
def list_news(
    ticker: Optional[str] = None,
    published_utc_gte: Optional[str] = None,
    published_utc_lte: Optional[str] = None,
    order: str = "desc",
    sort: str = "published_utc",
    limit: int = 50,
    client=Depends(get_client),
):
    params = {"order": order, "sort": sort}
    if ticker:
        params["ticker"] = ticker
    if published_utc_gte:
        params["published_utc.gte"] = published_utc_gte
    if published_utc_lte:
        params["published_utc.lte"] = published_utc_lte
    it = safe_call(client.list_ticker_news, **params, limit=1000)
    return take(it, limit)
