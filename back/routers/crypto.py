from fastapi import APIRouter, Depends, Query
from typing import Optional

from config import get_client
from utils import safe_call, take, to_dict

router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.get("/tickers")
def list_tickers(search: Optional[str] = None, active: bool = True,
                 limit: int = 100, client=Depends(get_client)):
    params = {"market": "crypto", "active": active, "limit": 1000}
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
    return to_dict(safe_call(client.get_grouped_daily_aggs, date, locale="global", market_type="crypto"))


@router.get("/daily-open-close/{ticker}/{date}")
def daily_open_close(ticker: str, date: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_daily_open_close_agg, ticker, date))


@router.get("/prev-close/{ticker}")
def prev_close(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_previous_close_agg, ticker))


@router.get("/trades/{ticker}")
def list_trades(ticker: str, timestamp: Optional[str] = None,
                limit: int = 1000, client=Depends(get_client)):
    params = {"timestamp": timestamp} if timestamp else {}
    it = safe_call(client.list_trades, ticker, limit=50000, **params)
    return take(it, limit)


@router.get("/trades/last")
def last_trade(from_: str = Query(..., alias="from"), to: str = Query(...),
               client=Depends(get_client)):
    return to_dict(safe_call(client.get_last_crypto_trade, from_, to))


@router.get("/snapshot/{ticker}")
def snapshot(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_snapshot_ticker, "crypto", ticker))


@router.get("/snapshot-all")
def snapshot_all(tickers: Optional[str] = None, client=Depends(get_client)):
    arr = tickers.split(",") if tickers else None
    return to_dict(safe_call(client.get_snapshot_all, "crypto", tickers=arr))


@router.get("/movers/{direction}")
def movers(direction: str, client=Depends(get_client)):
    if direction not in ("gainers", "losers"):
        return {"error": "direction must be 'gainers' or 'losers'"}
    return to_dict(safe_call(client.get_snapshot_direction, "crypto", direction))


@router.get("/book/{ticker}")
def order_book(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_snapshot_crypto_book, ticker))


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
