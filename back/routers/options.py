from fastapi import APIRouter, Depends, Query
from typing import Optional

from config import get_client
from utils import safe_call, take, to_dict

router = APIRouter(prefix="/options", tags=["options"])


# ---------------- Contracts ----------------

@router.get("/contracts")
def list_contracts(
    underlying_ticker: Optional[str] = None,
    contract_type: Optional[str] = None,
    expiration_date: Optional[str] = None,
    expiration_date_gte: Optional[str] = None,
    expiration_date_lte: Optional[str] = None,
    strike_price_gte: Optional[float] = None,
    strike_price_lte: Optional[float] = None,
    expired: Optional[bool] = None,
    limit: int = 100,
    client=Depends(get_client),
):
    params = {k: v for k, v in {
        "underlying_ticker": underlying_ticker,
        "contract_type": contract_type,
        "expiration_date": expiration_date,
        "expiration_date.gte": expiration_date_gte,
        "expiration_date.lte": expiration_date_lte,
        "strike_price.gte": strike_price_gte,
        "strike_price.lte": strike_price_lte,
        "expired": expired,
    }.items() if v is not None}
    it = safe_call(client.list_options_contracts, **params, limit=1000)
    return take(it, limit)


@router.get("/contracts/{options_ticker}")
def contract_details(options_ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_options_contract, options_ticker))


# ---------------- Aggregate bars ----------------

@router.get("/aggs/{options_ticker}")
def options_aggs(
    options_ticker: str,
    multiplier: int = 1,
    timespan: str = "day",
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    adjusted: bool = True,
    sort: str = "asc",
    limit: int = 5000,
    client=Depends(get_client),
):
    it = safe_call(client.list_aggs, options_ticker, multiplier, timespan, from_, to,
                   adjusted=adjusted, sort=sort, limit=50000)
    return take(it, limit)


@router.get("/daily-open-close/{options_ticker}/{date}")
def daily_open_close(options_ticker: str, date: str, adjusted: bool = True, client=Depends(get_client)):
    return to_dict(safe_call(client.get_daily_open_close_agg, options_ticker, date, adjusted=adjusted))


@router.get("/prev-close/{options_ticker}")
def prev_close(options_ticker: str, adjusted: bool = True, client=Depends(get_client)):
    return to_dict(safe_call(client.get_previous_close_agg, options_ticker, adjusted=adjusted))


# ---------------- Snapshots ----------------

@router.get("/chain/{underlying}")
def chain_snapshot(
    underlying: str,
    contract_type: Optional[str] = None,
    expiration_date: Optional[str] = None,
    expiration_date_gte: Optional[str] = None,
    expiration_date_lte: Optional[str] = None,
    strike_price_gte: Optional[float] = None,
    strike_price_lte: Optional[float] = None,
    limit: int = 250,
    client=Depends(get_client),
):
    params = {k: v for k, v in {
        "contract_type": contract_type,
        "expiration_date": expiration_date,
        "expiration_date.gte": expiration_date_gte,
        "expiration_date.lte": expiration_date_lte,
        "strike_price.gte": strike_price_gte,
        "strike_price.lte": strike_price_lte,
    }.items() if v is not None}
    it = safe_call(client.list_snapshot_options_chain, underlying, params=params)
    return take(it, limit)


@router.get("/snapshot/{underlying}/{options_ticker}")
def option_snapshot(underlying: str, options_ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_snapshot_option, underlying, options_ticker))


# ---------------- Trades & Quotes ----------------

@router.get("/trades/{options_ticker}")
def list_trades(options_ticker: str, timestamp: Optional[str] = None,
                limit: int = 1000, client=Depends(get_client)):
    params = {"timestamp": timestamp} if timestamp else {}
    it = safe_call(client.list_trades, options_ticker, limit=50000, **params)
    return take(it, limit)


@router.get("/trades/{options_ticker}/last")
def last_trade(options_ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_last_trade, options_ticker))


@router.get("/quotes/{options_ticker}")
def list_quotes(options_ticker: str, timestamp: Optional[str] = None,
                limit: int = 1000, client=Depends(get_client)):
    params = {"timestamp": timestamp} if timestamp else {}
    it = safe_call(client.list_quotes, options_ticker, limit=50000, **params)
    return take(it, limit)


# ---------------- Technical Indicators ----------------

@router.get("/indicators/sma/{options_ticker}")
def sma(options_ticker: str, timespan: str = "day", window: int = 50,
        series_type: str = "close", client=Depends(get_client)):
    return to_dict(safe_call(client.get_sma, options_ticker,
                              timespan=timespan, window=window, series_type=series_type))


@router.get("/indicators/ema/{options_ticker}")
def ema(options_ticker: str, timespan: str = "day", window: int = 50,
        series_type: str = "close", client=Depends(get_client)):
    return to_dict(safe_call(client.get_ema, options_ticker,
                              timespan=timespan, window=window, series_type=series_type))


@router.get("/indicators/macd/{options_ticker}")
def macd(options_ticker: str, timespan: str = "day",
         short_window: int = 12, long_window: int = 26, signal_window: int = 9,
         series_type: str = "close", client=Depends(get_client)):
    return to_dict(safe_call(
        client.get_macd, options_ticker,
        timespan=timespan, short_window=short_window, long_window=long_window,
        signal_window=signal_window, series_type=series_type,
    ))


@router.get("/indicators/rsi/{options_ticker}")
def rsi(options_ticker: str, timespan: str = "day", window: int = 14,
        series_type: str = "close", client=Depends(get_client)):
    return to_dict(safe_call(client.get_rsi, options_ticker,
                              timespan=timespan, window=window, series_type=series_type))
