from fastapi import APIRouter, Depends, Query
from typing import Optional

from config import get_client
from utils import safe_call, take, to_dict

router = APIRouter(prefix="/forex", tags=["forex"])


@router.get("/tickers")
def list_tickers(search: Optional[str] = None, active: bool = True,
                 limit: int = 100, client=Depends(get_client)):
    params = {"market": "fx", "active": active, "limit": 1000}
    if search:
        params["search"] = search
    it = safe_call(client.list_tickers, **params)
    return take(it, limit)


@router.get("/aggs/{ticker}")
def aggs(ticker: str, multiplier: int = 1, timespan: str = "day",
         from_: str = Query(..., alias="from"), to: str = Query(...),
         sort: str = "asc", limit: int = 5000, client=Depends(get_client)):
    it = safe_call(client.list_aggs, ticker, multiplier, timespan, from_, to, sort=sort, limit=50000)
    return take(it, limit)


@router.get("/grouped-daily/{date}")
def grouped_daily(date: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_grouped_daily_aggs, date, locale="global", market_type="fx"))


@router.get("/daily-open-close/{ticker}/{date}")
def daily_open_close(ticker: str, date: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_daily_open_close_agg, ticker, date))


@router.get("/prev-close/{ticker}")
def prev_close(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_previous_close_agg, ticker))


@router.get("/quotes/{ticker}")
def list_quotes(ticker: str, timestamp: Optional[str] = None,
                limit: int = 1000, client=Depends(get_client)):
    params = {"timestamp": timestamp} if timestamp else {}
    it = safe_call(client.list_quotes, ticker, limit=50000, **params)
    return take(it, limit)


@router.get("/quotes/last")
def last_quote(from_: str = Query(..., alias="from"), to: str = Query(...),
               client=Depends(get_client)):
    return to_dict(safe_call(client.get_last_forex_quote, from_, to))


@router.get("/snapshot/{ticker}")
def snapshot(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_snapshot_ticker, "forex", ticker))


@router.get("/snapshot-all")
def snapshot_all(tickers: Optional[str] = None, client=Depends(get_client)):
    arr = tickers.split(",") if tickers else None
    return to_dict(safe_call(client.get_snapshot_all, "forex", tickers=arr))


@router.get("/movers/{direction}")
def movers(direction: str, client=Depends(get_client)):
    if direction not in ("gainers", "losers"):
        return {"error": "direction must be 'gainers' or 'losers'"}
    return to_dict(safe_call(client.get_snapshot_direction, "forex", direction))


@router.get("/convert")
def convert(
    from_currency: str = Query(..., alias="from"),
    to: str = Query(...),
    amount: float = 1.0,
    precision: int = 2,
    client=Depends(get_client),
):
    return to_dict(safe_call(client.get_real_time_currency_conversion,
                              from_currency, to, amount=amount, precision=precision))


@router.get("/indicators/sma/{ticker}")
def sma(ticker: str, timespan: str = "day", window: int = 50, client=Depends(get_client)):
    return to_dict(safe_call(client.get_sma, ticker, timespan=timespan, window=window))


@router.get("/indicators/ema/{ticker}")
def ema(ticker: str, timespan: str = "day", window: int = 50, client=Depends(get_client)):
    return to_dict(safe_call(client.get_ema, ticker, timespan=timespan, window=window))


@router.get("/indicators/macd/{ticker}")
def macd(ticker: str, timespan: str = "day",
         short_window: int = 12, long_window: int = 26, signal_window: int = 9,
         client=Depends(get_client)):
    return to_dict(safe_call(client.get_macd, ticker, timespan=timespan,
                              short_window=short_window, long_window=long_window,
                              signal_window=signal_window))


@router.get("/indicators/rsi/{ticker}")
def rsi(ticker: str, timespan: str = "day", window: int = 14, client=Depends(get_client)):
    return to_dict(safe_call(client.get_rsi, ticker, timespan=timespan, window=window))
