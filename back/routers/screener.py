"""GET /screener/{universe} — sp500 | nasdaq100 | combined."""
from __future__ import annotations
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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
_snapshot_memo: dict[str, tuple[float, list]] = {}
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
    """Load a universe JSON. lru_cache so repeated reads hit memory.

    Returns tuple (immutable) so lru_cache can cache it safely.
    """
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


def _get_snapshots(client) -> dict[str, object]:
    """Return ticker → snapshot dict, using a 10s in-process memo cache."""
    now = time.monotonic()
    cached = _snapshot_memo.get("all_stocks")
    if cached and (now - cached[0]) < SNAPSHOT_TTL_S:
        snaps = cached[1]
    else:
        snaps = client.get_snapshot_all("stocks")
        _snapshot_memo["all_stocks"] = (now, snaps)
    return {s.ticker: s for s in snaps}


def _refresh_metadata(client, cache: MetadataCache, ticker: str) -> dict:
    """Fetch market_cap + pe_ratio for one ticker and store. Returns the new entry."""
    try:
        details = client.get_ticker_details(ticker)
        market_cap = getattr(details, "market_cap", None)
    except Exception:
        market_cap = None
    try:
        ratios = next(iter(client.list_ratios(ticker=ticker)), None)
        pe_ratio = getattr(ratios, "price_to_earnings_ratio", None) if ratios else None
    except Exception:
        pe_ratio = None
    cache.put(ticker, market_cap, pe_ratio)
    return {"market_cap": market_cap, "pe_ratio": pe_ratio}


@router.get("/{universe}", response_model=list[ScreenerRow])
def screener(universe: str):
    client = get_client()
    tickers = _load_universe(universe)
    snapshots = _get_snapshots(client)
    cache = MetadataCache(METADATA_DB)

    rows: list[ScreenerRow] = []
    for t in tickers:
        ticker = t["ticker"]
        snap = snapshots.get(ticker)

        cached = cache.get(ticker)
        if cache.is_stale(cached):
            md = _refresh_metadata(client, cache, ticker)
        else:
            md = cached

        rows.append(ScreenerRow(
            ticker=ticker,
            name=t["name"],
            sector=t["sector"],
            price=getattr(snap.day, "close", None) if snap else None,
            change_pct=getattr(snap, "todays_change_perc", None) if snap else None,
            volume=getattr(snap.day, "volume", None) if snap else None,
            market_cap=md.get("market_cap") if md else None,
            pe_ratio=md.get("pe_ratio") if md else None,
        ))
    return rows
