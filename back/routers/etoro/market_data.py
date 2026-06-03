"""eToro market-data endpoints (search, instruments, rates, candles, reference)."""
from typing import Optional
from fastapi import APIRouter, Depends

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro/market-data", tags=["etoro:market-data"])


@router.get("/search")
def search(fields: str, searchText: Optional[str] = None,
           internalSymbolFull: Optional[str] = None,
           pageSize: Optional[int] = None, pageNumber: Optional[int] = None,
           sort: Optional[str] = None,
           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/search", params=drop_none({
        "fields": fields, "searchText": searchText,
        "internalSymbolFull": internalSymbolFull,
        "pageSize": pageSize, "pageNumber": pageNumber, "sort": sort}))


@router.get("/instruments")
def instruments(instrumentIds: Optional[str] = None, exchangeIds: Optional[str] = None,
                stocksIndustryIds: Optional[str] = None, instrumentTypeIds: Optional[str] = None,
                client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instruments", params=drop_none({
        "instrumentIds": instrumentIds, "exchangeIds": exchangeIds,
        "stocksIndustryIds": stocksIndustryIds, "instrumentTypeIds": instrumentTypeIds}))


@router.get("/instruments/rates")
def rates(instrumentIds: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instruments/rates",
                          params={"instrumentIds": instrumentIds})


@router.get("/instruments/history/closing-price")
def closing_price(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instruments/history/closing-price")


@router.get("/instruments/{instrument_id}/history/candles/{direction}/{interval}/{candles_count}")
def candles(instrument_id: int, direction: str, interval: str, candles_count: int,
            client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "GET",
        f"/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{candles_count}")


@router.get("/exchanges")
def exchanges(exchangeIds: Optional[str] = None,
              client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/exchanges",
                          params=drop_none({"exchangeIds": exchangeIds}))


@router.get("/instrument-types")
def instrument_types(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instrument-types")


@router.get("/stocks-industries")
def stocks_industries(stocksIndustryIds: Optional[str] = None,
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/stocks-industries",
                          params=drop_none({"stocksIndustryIds": stocksIndustryIds}))
