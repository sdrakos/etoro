"""GET /screener/{universe} — sp500 | nasdaq100 | combined.

Uses get_grouped_daily_aggs (free tier) × 2 days to compute price + change_pct.
Metadata (market_cap, P/E) is best-effort: on Massive Basic tier the
list_ratios endpoint returns 401, so those fields stay null. Upgrade to
Starter+ to populate them.
"""
from __future__ import annotations
import json
import time
from datetime import date as _date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_client as _real_get_client
from data_cache.metadata_cache import MetadataCache


def get_client():
    """Indirection so tests can monkeypatch routers.screener.get_client."""
    return _real_get_client()

router = APIRouter(prefix="/screener", tags=["screener"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
METADATA_DB = Path.home() / ".etoro" / "screener_metadata.db"
METADATA_DB.parent.mkdir(parents=True, exist_ok=True)

# Snapshot memo cache: shared across universes, 10s TTL
_snapshot_memo: dict[str, tuple[float, object]] = {}
SNAPSHOT_TTL_S = 10


class ScreenerRow(BaseModel):
    ticker: str
    name: str
    sector: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
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


def _get_two_recent_days(client) -> tuple[dict, dict]:
    """Find most recent 2 US business days with data.

    Returns (today_map, prev_map) where each is {ticker: agg} with .close
    and .volume attributes. Empty dicts if Massive returns nothing for the
    last ~10 days (holidays, weekends, or API error).

    Memoised 10s server-side so back-to-back screener requests reuse it.
    Uses get_grouped_daily_aggs which is included in Massive Basic (free).
    """
    cache_key = "grouped_daily_pair"
    now = time.monotonic()
    cached = _snapshot_memo.get(cache_key)
    if cached and (now - cached[0]) < SNAPSHOT_TTL_S:
        return cached[1]  # type: ignore[return-value]

    days_found: list[dict] = []
    d = _date.today() - timedelta(days=1)
    attempts = 0
    while len(days_found) < 2 and attempts < 10:
        if d.weekday() < 5:  # Mon-Fri (skip weekends)
            try:
                aggs = client.get_grouped_daily_aggs(d.isoformat())
                aggs_list = list(aggs) if aggs else []
                if aggs_list:
                    days_found.append({a.ticker: a for a in aggs_list})
            except Exception:
                pass
        d -= timedelta(days=1)
        attempts += 1

    if len(days_found) >= 2:
        result = (days_found[0], days_found[1])
    elif len(days_found) == 1:
        result = (days_found[0], {})
    else:
        result = ({}, {})

    _snapshot_memo[cache_key] = (now, result)
    return result


def _refresh_metadata(client, cache: MetadataCache, ticker: str,
                     skip_flag: list[bool]) -> dict:
    """Fetch market_cap + pe_ratio. Circuit-breaks on auth errors.

    `skip_flag` is a single-element list used as a mutable bool across the
    whole request — once we see a 401/403/NOT_AUTHORIZED on metadata calls,
    we stop hammering the API for the rest of this request.
    """
    if skip_flag[0]:
        return {"market_cap": None, "pe_ratio": None}

    market_cap = None
    pe_ratio = None
    auth_error_markers = ("401", "403", "NOT_AUTHORIZED", "not entitled")

    try:
        details = client.get_ticker_details(ticker)
        market_cap = getattr(details, "market_cap", None)
    except Exception as e:
        if any(m in str(e) for m in auth_error_markers):
            skip_flag[0] = True

    if not skip_flag[0]:
        try:
            ratios = next(iter(client.list_ratios(ticker=ticker)), None)
            pe_ratio = getattr(ratios, "price_to_earnings_ratio", None) if ratios else None
        except Exception as e:
            if any(m in str(e) for m in auth_error_markers):
                skip_flag[0] = True

    cache.put(ticker, market_cap, pe_ratio)
    return {"market_cap": market_cap, "pe_ratio": pe_ratio}


@router.get("/{universe}", response_model=list[ScreenerRow])
def screener(universe: str):
    """Return the screener rows for a universe.

    market_cap and pe_ratio come from the cache only — they are NOT refreshed
    inline here because Massive Basic tier rate-limits metadata calls to 5/min
    and we have ~500 tickers. Use POST /screener/refresh-metadata to populate
    the cache out-of-band (rolling refresh, respects rate limits).
    """
    client = get_client()
    tickers = _load_universe(universe)
    today_map, prev_map = _get_two_recent_days(client)
    cache = MetadataCache(METADATA_DB)

    rows: list[ScreenerRow] = []
    for t in tickers:
        ticker = t["ticker"]
        today = today_map.get(ticker)
        prev = prev_map.get(ticker)

        price = getattr(today, "close", None) if today else None
        volume = getattr(today, "volume", None) if today else None
        prev_close = getattr(prev, "close", None) if prev else None

        change_pct: Optional[float] = None
        if price is not None and prev_close is not None and prev_close > 0:
            change_pct = ((price - prev_close) / prev_close) * 100

        # Cached-only metadata — no inline API calls. None if not yet cached.
        cached_md = cache.get(ticker)

        rows.append(ScreenerRow(
            ticker=ticker,
            name=t["name"],
            sector=t["sector"],
            price=price,
            change_pct=change_pct,
            volume=volume,
            market_cap=cached_md.get("market_cap") if cached_md else None,
            pe_ratio=cached_md.get("pe_ratio") if cached_md else None,
        ))
    return rows
