"""GET /screener/{universe} — sp500 | nasdaq100 | combined, priced from eToro.

Live bid/ask come from eToro /rates; daily change %, sentiment, and exchange come
from a cached eToro instrument catalog (refresh via POST /screener/refresh-etoro-catalog).
market_cap / pe_ratio remain best-effort from the Massive metadata cache.
"""
from __future__ import annotations
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import get_client as _real_get_client
from etoro_api.server import get_server_client
from data_cache.etoro_catalog import EtoroCatalog
from data_cache.metadata_cache import MetadataCache


def get_client():
    """Indirection so tests can monkeypatch routers.screener.get_client (Massive metadata)."""
    return _real_get_client()


router = APIRouter(prefix="/screener", tags=["screener"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
METADATA_DB = Path.home() / ".etoro" / "screener_metadata.db"
CATALOG_DB = Path.home() / ".etoro" / "etoro_catalog.db"
METADATA_DB.parent.mkdir(parents=True, exist_ok=True)

_snapshot_memo: dict[str, tuple[float, dict]] = {}
SNAPSHOT_TTL_S = 10
RATES_BATCH = 100
CATALOG_REFRESH_S = 90
_last_refresh_ts: Optional[float] = None
_CATEGORY_MAP = {
    "stocks": "Stocks", "crypto": "Crypto", "etf": "ETF",
    "indices": "Indices", "commodities": "Commodity", "currencies": "Forex",
}
_STOCK_CLASSES = {"Stocks", "ETF", "Indices", None}


class ScreenerRow(BaseModel):
    ticker: str
    name: str
    sector: str
    instrument_id: Optional[int] = None
    exchange: Optional[str] = None
    price: Optional[float] = None
    sell: Optional[float] = None
    buy: Optional[float] = None
    change_pct: Optional[float] = None
    sentiment_buy_pct: Optional[float] = None
    is_open: Optional[bool] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None


class CategoryPage(BaseModel):
    items: list[ScreenerRow]
    total: int
    page: int
    pageSize: int
    category: str


@lru_cache(maxsize=4)
def _load_universe_file(name: str) -> tuple[dict, ...]:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, f"Universe file not found: {name}")
    return tuple(json.loads(path.read_text(encoding="utf-8"))["tickers"])


def _load_universe(universe: str) -> list[dict]:
    if universe == "combined":
        seen: dict[str, dict] = {}
        for src in ("sp500", "nasdaq100"):
            for t in _load_universe_file(src):
                seen.setdefault(t["ticker"], t)
        return list(seen.values())
    if universe in ("sp500", "nasdaq100"):
        return list(_load_universe_file(universe))
    raise HTTPException(404, f"Unknown universe: {universe}")


def refresh_catalog() -> dict:
    """Page /instruments/discover (lean items) into the catalog cache. Returns counts."""
    client = get_server_client()
    catalog = EtoroCatalog(CATALOG_DB)
    page, page_size, total_upserted = 1, 1000, 0
    while page <= 50:
        res = client.request("GET", "/api/v1/instruments/discover",
                             params={"pageSize": page_size, "page": page})
        items = res.get("items", []) if isinstance(res, dict) else []
        if not items:
            break
        rows = [{
            "symbol": it.get("symbol"),
            "instrument_id": it.get("instrumentId"),
            "exchange_name": it.get("exchangeName"),
            "display_name": it.get("displayName"),
            "current_rate": it.get("currentRate"),
            "asset_class": it.get("assetClass"),
        } for it in items]
        total_upserted += catalog.upsert(rows)
        if len(items) < page_size:
            break
        page += 1
    return {"instruments": total_upserted}


@router.post("/refresh-etoro-catalog")
def refresh_etoro_catalog():
    return refresh_catalog()


def _fetch_rates(client, instrument_ids: list[int]) -> dict[int, dict]:
    """Bulk live rates, batched (eToro wants repeated instrumentIds params)."""
    cache_key = "rates:" + ",".join(map(str, instrument_ids))
    now = time.monotonic()
    cached = _snapshot_memo.get(cache_key)
    if cached and (now - cached[0]) < SNAPSHOT_TTL_S:
        return cached[1]
    out: dict[int, dict] = {}
    for i in range(0, len(instrument_ids), RATES_BATCH):
        batch = [str(x) for x in instrument_ids[i:i + RATES_BATCH]]
        res = client.request("GET", "/api/v1/market-data/instruments/rates",
                             params={"instrumentIds": batch})
        for r in (res.get("rates", []) if isinstance(res, dict) else []):
            iid = r.get("instrumentID")
            if iid is not None:
                out[int(iid)] = r
    _snapshot_memo[cache_key] = (now, out)
    return out


def _fetch_closing(client) -> dict[int, dict]:
    """Bulk previous-close + market-open status for all instruments (memoized)."""
    now = time.monotonic()
    cached = _snapshot_memo.get("closing")
    if cached and (now - cached[0]) < SNAPSHOT_TTL_S:
        return cached[1]
    res = client.request("GET", "/api/v1/market-data/instruments/history/closing-price")
    out: dict[int, dict] = {}
    for c in (res if isinstance(res, list) else []):
        iid = c.get("instrumentId")
        if iid is not None:
            out[int(iid)] = c
    _snapshot_memo["closing"] = (now, out)
    return out


def _build_rows(universe: str) -> list[ScreenerRow]:
    tickers = _load_universe(universe)
    catalog = EtoroCatalog(CATALOG_DB)
    mapped = catalog.get_many([t["ticker"] for t in tickers])

    def _is_stock(c):
        return c is not None and c.get("asset_class") in _STOCK_CLASSES
    ids = [mapped[t["ticker"]]["instrument_id"] for t in tickers
           if _is_stock(mapped.get(t["ticker"]))]
    client = get_server_client()
    rates = _fetch_rates(client, ids) if ids else {}
    closing = _fetch_closing(client) if ids else {}

    md_cache = MetadataCache(METADATA_DB)
    rows: list[ScreenerRow] = []
    for t in tickers:
        ticker = t["ticker"]
        cat = mapped.get(ticker)
        if cat is not None and cat.get("asset_class") not in _STOCK_CLASSES:
            cat = None
        iid = cat["instrument_id"] if cat else None
        rate = rates.get(iid) if iid is not None else None
        clo = closing.get(iid) if iid is not None else None
        md = md_cache.get(ticker)

        last = rate.get("lastExecution") if rate else None
        if last is None and cat:
            last = cat.get("current_rate")
        prev = clo.get("officialClosingPrice") if clo else None
        change_pct = None
        if last is not None and prev not in (None, 0):
            change_pct = (last - prev) / prev * 100

        rows.append(ScreenerRow(
            ticker=ticker, name=t["name"], sector=t["sector"],
            instrument_id=iid,
            exchange=cat.get("exchange_name") if cat else None,
            price=last,
            sell=rate.get("bid") if rate else None,
            buy=rate.get("ask") if rate else None,
            change_pct=change_pct,
            sentiment_buy_pct=None,
            is_open=clo.get("isMarketOpen") if clo else None,
            volume=None,
            market_cap=md.get("market_cap") if md else None,
            pe_ratio=md.get("pe_ratio") if md else None,
        ))
    return rows


@router.get("/movers", response_model=list[ScreenerRow])
def movers(universe: str = Query("combined"),
           direction: str = Query("gainers"),
           limit: int = Query(20)):
    rows = [r for r in _build_rows(universe) if r.change_pct is not None]
    rows.sort(key=lambda r: r.change_pct, reverse=(direction != "losers"))
    return rows[:max(0, limit)]


def _enrich_category(rows: list[dict], client, closing: dict, with_rates: bool) -> list[ScreenerRow]:
    ids = [r["instrument_id"] for r in rows if r.get("instrument_id") is not None]
    rates = _fetch_rates(client, ids) if (with_rates and ids) else {}
    out: list[ScreenerRow] = []
    for r in rows:
        iid = r.get("instrument_id")
        rate = rates.get(iid) if iid is not None else None
        last = (rate.get("lastExecution") if rate else None)
        if last is None:
            last = r.get("current_rate")
        clo = closing.get(iid) if iid is not None else None
        prev = clo.get("officialClosingPrice") if clo else None
        change_pct = (last - prev) / prev * 100 if (last is not None and prev not in (None, 0)) else None
        out.append(ScreenerRow(
            ticker=r.get("symbol"), name=r.get("display_name") or r.get("symbol"),
            sector=r.get("asset_class") or "",
            instrument_id=iid, exchange=r.get("exchange_name"),
            price=last, sell=rate.get("bid") if rate else None,
            buy=rate.get("ask") if rate else None, change_pct=change_pct,
            sentiment_buy_pct=None,
            is_open=clo.get("isMarketOpen") if clo else None,
            volume=None, market_cap=None, pe_ratio=None,
        ))
    return out


@router.get("/category/{category}", response_model=CategoryPage)
def category_browse(category: str, page: int = Query(1), pageSize: int = Query(50),
                    sort: str = Query("change"), dir: str = Query("desc"),
                    q: Optional[str] = Query(None)):
    asset = _CATEGORY_MAP.get(category.lower())
    if asset is None:
        raise HTTPException(404, f"Unknown category: {category}")
    page = max(1, page)
    page_size = max(1, min(pageSize, 200))
    catalog = EtoroCatalog(CATALOG_DB)
    client = get_server_client()
    closing = _fetch_closing(client)

    if sort == "name":
        rows, total = catalog.query(asset, q, "name", page, page_size)
        items = _enrich_category(rows, client, closing, with_rates=True)
        return CategoryPage(items=items, total=total, page=page, pageSize=page_size,
                            category=category.lower())

    all_rows = catalog.all_for_category(asset, q)
    total = len(all_rows)
    enriched = _enrich_category(all_rows, client, closing, with_rates=False)
    keyf = ((lambda x: x.change_pct if x.change_pct is not None else float("-inf"))
            if sort == "change"
            else (lambda x: x.price if x.price is not None else float("-inf")))
    enriched.sort(key=keyf, reverse=(dir != "asc"))
    start = (page - 1) * page_size
    page_items = enriched[start:start + page_size]
    ids = [r.instrument_id for r in page_items if r.instrument_id is not None]
    rates = _fetch_rates(client, ids) if ids else {}
    for r in page_items:
        rate = rates.get(r.instrument_id)
        if rate:
            r.sell = rate.get("bid")
            r.buy = rate.get("ask")
            if rate.get("lastExecution") is not None:
                r.price = rate.get("lastExecution")
    return CategoryPage(items=page_items, total=total, page=page, pageSize=page_size,
                        category=category.lower())


def _refresh_once() -> dict:
    """One catalog refresh; records the timestamp. Used by the background loop."""
    global _last_refresh_ts
    result = refresh_catalog()
    _last_refresh_ts = time.time()
    return result


@router.get("/catalog-status")
def catalog_status():
    cat = EtoroCatalog(CATALOG_DB)
    age = (time.time() - _last_refresh_ts) if _last_refresh_ts is not None else None
    return {"instruments": cat.count(), "last_refresh_age_s": age}


@router.get("/{universe}", response_model=list[ScreenerRow])
def screener(universe: str):
    return _build_rows(universe)
