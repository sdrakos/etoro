from fastapi import APIRouter, Depends, Query
from typing import Optional

from config import get_client
from utils import safe_call, take, to_dict

router = APIRouter(prefix="/stocks", tags=["stocks"])


# ---------------- Tickers ----------------

@router.get("/tickers")
def list_tickers(
    market: str = "stocks",
    active: bool = True,
    search: Optional[str] = None,
    exchange: Optional[str] = None,
    cusip: Optional[str] = None,
    cik: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 100,
    client=Depends(get_client),
):
    it = safe_call(
        client.list_tickers,
        market=market, active=active, search=search,
        exchange=exchange, cusip=cusip, cik=cik, date=date, limit=1000,
    )
    return take(it, limit)


@router.get("/tickers/{ticker}")
def ticker_details(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_ticker_details, ticker))


@router.get("/ticker-types")
def ticker_types(asset_class: Optional[str] = None, locale: Optional[str] = None, client=Depends(get_client)):
    return to_dict(safe_call(client.get_ticker_types, asset_class=asset_class, locale=locale))


@router.get("/tickers/{ticker}/related")
def related_companies(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_related_companies, ticker))


# ---------------- Aggregate bars ----------------

@router.get("/aggs/{ticker}")
def aggs(
    ticker: str,
    multiplier: int = 1,
    timespan: str = "day",
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    adjusted: bool = True,
    sort: str = "asc",
    limit: int = 5000,
    client=Depends(get_client),
):
    it = safe_call(
        client.list_aggs,
        ticker, multiplier, timespan, from_, to,
        adjusted=adjusted, sort=sort, limit=50000,
    )
    return take(it, limit)


@router.get("/grouped-daily/{date}")
def grouped_daily(date: str, adjusted: bool = True, client=Depends(get_client)):
    return to_dict(safe_call(client.get_grouped_daily_aggs, date, adjusted=adjusted))


@router.get("/daily-open-close/{ticker}/{date}")
def daily_open_close(ticker: str, date: str, adjusted: bool = True, client=Depends(get_client)):
    return to_dict(safe_call(client.get_daily_open_close_agg, ticker, date, adjusted=adjusted))


@router.get("/prev-close/{ticker}")
def prev_close(ticker: str, adjusted: bool = True, client=Depends(get_client)):
    return to_dict(safe_call(client.get_previous_close_agg, ticker, adjusted=adjusted))


# ---------------- Snapshots ----------------

@router.get("/snapshot/{ticker}")
def snapshot_ticker(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_snapshot_ticker, "stocks", ticker))


@router.get("/snapshot-all")
def snapshot_all(tickers: Optional[str] = None, include_otc: bool = False, client=Depends(get_client)):
    arr = tickers.split(",") if tickers else None
    return to_dict(safe_call(client.get_snapshot_all, "stocks", tickers=arr, include_otc=include_otc))


@router.get("/snapshot-universal")
def universal_snapshot(tickers: str, client=Depends(get_client)):
    arr = tickers.split(",")
    return to_dict(safe_call(client.list_universal_snapshots, ticker_any_of=arr))


@router.get("/movers/{direction}")
def movers(direction: str, include_otc: bool = False, client=Depends(get_client)):
    if direction not in ("gainers", "losers"):
        return {"error": "direction must be 'gainers' or 'losers'"}
    return to_dict(safe_call(client.get_snapshot_direction, "stocks", direction, include_otc=include_otc))


# ---------------- Trades & Quotes ----------------

@router.get("/trades/{ticker}")
def list_trades(
    ticker: str,
    timestamp: Optional[str] = None,
    limit: int = 1000,
    client=Depends(get_client),
):
    params = {"timestamp": timestamp} if timestamp else {}
    it = safe_call(client.list_trades, ticker, limit=50000, **params)
    return take(it, limit)


@router.get("/trades/{ticker}/last")
def last_trade(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_last_trade, ticker))


@router.get("/quotes/{ticker}")
def list_quotes(
    ticker: str,
    timestamp: Optional[str] = None,
    limit: int = 1000,
    client=Depends(get_client),
):
    params = {"timestamp": timestamp} if timestamp else {}
    it = safe_call(client.list_quotes, ticker, limit=50000, **params)
    return take(it, limit)


@router.get("/quotes/{ticker}/last")
def last_quote(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_last_quote, ticker))


# ---------------- Technical Indicators ----------------

def _indicator_args(timespan: str, window: int, series_type: str, adjusted: bool, timestamp: Optional[str]):
    args = {"timespan": timespan, "window": window, "series_type": series_type, "adjusted": adjusted}
    if timestamp:
        args["timestamp"] = timestamp
    return args


@router.get("/indicators/sma/{ticker}")
def sma(ticker: str, timespan: str = "day", window: int = 50, series_type: str = "close",
        adjusted: bool = True, timestamp: Optional[str] = None, client=Depends(get_client)):
    return to_dict(safe_call(client.get_sma, ticker, **_indicator_args(timespan, window, series_type, adjusted, timestamp)))


@router.get("/indicators/ema/{ticker}")
def ema(ticker: str, timespan: str = "day", window: int = 50, series_type: str = "close",
        adjusted: bool = True, timestamp: Optional[str] = None, client=Depends(get_client)):
    return to_dict(safe_call(client.get_ema, ticker, **_indicator_args(timespan, window, series_type, adjusted, timestamp)))


@router.get("/indicators/macd/{ticker}")
def macd(
    ticker: str,
    timespan: str = "day",
    short_window: int = 12,
    long_window: int = 26,
    signal_window: int = 9,
    series_type: str = "close",
    adjusted: bool = True,
    client=Depends(get_client),
):
    return to_dict(safe_call(
        client.get_macd, ticker,
        timespan=timespan, short_window=short_window, long_window=long_window,
        signal_window=signal_window, series_type=series_type, adjusted=adjusted,
    ))


@router.get("/indicators/rsi/{ticker}")
def rsi(ticker: str, timespan: str = "day", window: int = 14, series_type: str = "close",
        adjusted: bool = True, client=Depends(get_client)):
    return to_dict(safe_call(client.get_rsi, ticker,
                              timespan=timespan, window=window, series_type=series_type, adjusted=adjusted))


# ---------------- Corporate Actions ----------------

@router.get("/ipos")
def ipos(ipo_status: Optional[str] = None, ticker: Optional[str] = None,
         limit: int = 100, client=Depends(get_client)):
    params = {}
    if ipo_status:
        params["ipo_status"] = ipo_status
    if ticker:
        params["ticker"] = ticker
    it = safe_call(client.list_ipos, **params, limit=1000)
    return take(it, limit)


@router.get("/splits")
def splits(ticker: Optional[str] = None, execution_date: Optional[str] = None,
           limit: int = 100, client=Depends(get_client)):
    params = {}
    if ticker:
        params["ticker"] = ticker
    if execution_date:
        params["execution_date"] = execution_date
    it = safe_call(client.list_splits, **params, limit=1000)
    return take(it, limit)


@router.get("/dividends")
def dividends(ticker: Optional[str] = None, ex_dividend_date: Optional[str] = None,
              limit: int = 100, client=Depends(get_client)):
    params = {}
    if ticker:
        params["ticker"] = ticker
    if ex_dividend_date:
        params["ex_dividend_date"] = ex_dividend_date
    it = safe_call(client.list_dividends, **params, limit=1000)
    return take(it, limit)


@router.get("/ticker-events/{ticker_id}")
def ticker_events(ticker_id: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_ticker_events, ticker_id))


# ---------------- Fundamentals ----------------

@router.get("/financials/balance-sheets/{ticker}")
def balance_sheets(ticker: str, limit: int = 20, client=Depends(get_client)):
    it = safe_call(client.list_balance_sheets, ticker=ticker, limit=100)
    return take(it, limit)


@router.get("/financials/cash-flow/{ticker}")
def cash_flow(ticker: str, limit: int = 20, client=Depends(get_client)):
    it = safe_call(client.list_cash_flow_statements, ticker=ticker, limit=100)
    return take(it, limit)


@router.get("/financials/income/{ticker}")
def income_statements(ticker: str, limit: int = 20, client=Depends(get_client)):
    it = safe_call(client.list_income_statements, ticker=ticker, limit=100)
    return take(it, limit)


@router.get("/financials/ratios/{ticker}")
def ratios(ticker: str, limit: int = 100, client=Depends(get_client)):
    it = safe_call(client.list_ratios, ticker=ticker, limit=1000)
    return take(it, limit)


@router.get("/short-interest/{ticker}")
def short_interest(ticker: str, limit: int = 50, client=Depends(get_client)):
    it = safe_call(client.list_short_interest, ticker=ticker, limit=1000)
    return take(it, limit)


@router.get("/short-volume/{ticker}")
def short_volume(ticker: str, limit: int = 50, client=Depends(get_client)):
    it = safe_call(client.list_short_volume, ticker=ticker, limit=1000)
    return take(it, limit)


@router.get("/float/{ticker}")
def public_float(ticker: str, client=Depends(get_client)):
    return to_dict(safe_call(client.get_float, ticker))


# ---------------- News ----------------

@router.get("/news")
def ticker_news(
    ticker: Optional[str] = None,
    published_utc_gte: Optional[str] = None,
    published_utc_lte: Optional[str] = None,
    order: str = "desc",
    limit: int = 50,
    client=Depends(get_client),
):
    params = {"order": order}
    if ticker:
        params["ticker"] = ticker
    if published_utc_gte:
        params["published_utc_gte"] = published_utc_gte
    if published_utc_lte:
        params["published_utc_lte"] = published_utc_lte
    it = safe_call(client.list_ticker_news, **params, limit=1000)
    return take(it, limit)
