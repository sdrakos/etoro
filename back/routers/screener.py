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

    ids = [mapped[t["ticker"]]["instrument_id"] for t in tickers if t["ticker"] in mapped]
    client = get_server_client()
    rates = _fetch_rates(client, ids) if ids else {}
    closing = _fetch_closing(client) if ids else {}

    md_cache = MetadataCache(METADATA_DB)
    rows: list[ScreenerRow] = []
    for t in tickers:
        ticker = t["ticker"]
        cat = mapped.get(ticker)
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


@router.get("/{universe}", response_model=list[ScreenerRow])
def screener(universe: str):
    return _build_rows(universe)
