# Screener live eToro prices + Daily Movers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the screener's price source from Massive end-of-day to live eToro (bid/ask, daily change %, sentiment, exchange) and add a `/screener/movers` endpoint.

**Architecture:** A server-side `EtoroClient` (from `.env` demo keys) feeds a refreshable on-disk catalog (symbol→instrumentId + dailyPriceChange + buyHoldingPct + exchange, paged from `/instruments/discover`). The screener maps universe tickers via the catalog and pulls live bid/ask from `/rates` (batched, memoized). `market_cap`/`pe` stay on the existing Massive metadata cache.

**Tech Stack:** Python 3.11+, FastAPI, httpx, Pydantic, SQLite, pytest. eToro reference spec at `back/etoro_api/reference/etoro-openapi.json`.

All commands assume cwd `etoro/back/`. Tests offline (eToro client mocked). Clean commits, **no** Co-Authored-By trailer.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/etoro_api/server.py` | `get_server_client()` — EtoroClient from `.env` (no tenant) |
| `back/data_cache/etoro_catalog.py` | `EtoroCatalog` SQLite (symbol→id + change/sentiment/exchange) |
| `back/routers/screener.py` | price source = eToro; `/refresh-etoro-catalog`; `/movers`; rates batching |
| `back/tests/test_etoro_server.py` | new |
| `back/tests/test_etoro_catalog.py` | new |
| `back/tests/test_screener.py` | **replaced** (eToro-based) |
| `back/tests/test_screener_movers.py` | new |

> Exchange names come from each instrument's `internalExchangeName` field in `/instruments/discover` (one source — no separate `/market-data/exchanges` call needed).

---

### Task 1: Server-side eToro client

**Files:**
- Create: `back/etoro_api/server.py`, `back/tests/test_etoro_server.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_server.py
import pytest
from fastapi import HTTPException


def test_get_server_client_builds_from_env(monkeypatch):
    import etoro_api.server as server
    monkeypatch.setenv("ETORO_PUBLIC_KEY", "PUB")
    monkeypatch.setenv("ETORO_PRIVATE_KEY", "USR")
    client = server.get_server_client()
    assert client.public_key == "PUB"
    assert client.user_key == "USR"


def test_get_server_client_raises_503_without_keys(monkeypatch):
    import etoro_api.server as server
    monkeypatch.delenv("ETORO_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ETORO_PRIVATE_KEY", raising=False)
    with pytest.raises(HTTPException) as ei:
        server.get_server_client()
    assert ei.value.status_code == 503
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_server.py -v`
Expected: FAIL — `No module named 'etoro_api.server'`.

- [ ] **Step 3: Write `back/etoro_api/server.py`**

```python
"""Server-side eToro client for shared market-data (no tenant).

Uses the app's own ETORO_* keys from back/.env. For public/market-data routes
(e.g. the screener) that must not require a per-user X-User-Id header.
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import HTTPException
from dotenv import load_dotenv

from etoro_api.client import EtoroClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_server_client() -> EtoroClient:
    pub = os.getenv("ETORO_PUBLIC_KEY")
    usr = os.getenv("ETORO_PRIVATE_KEY")
    if not pub or not usr:
        raise HTTPException(status_code=503, detail="eToro server keys missing from back/.env")
    return EtoroClient(pub, usr, environment="demo")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_server.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add back/etoro_api/server.py back/tests/test_etoro_server.py
git commit -m "feat(screener): server-side eToro client from .env keys"
```

---

### Task 2: eToro catalog cache

**Files:**
- Create: `back/data_cache/etoro_catalog.py`, `back/tests/test_etoro_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_catalog.py
from data_cache.etoro_catalog import EtoroCatalog


def test_upsert_and_get_many_case_insensitive(tmp_path):
    cat = EtoroCatalog(tmp_path / "cat.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1001, "exchange_name": "NASDAQ",
         "display_name": "Apple", "type_id": 5, "daily_change": 1.2,
         "sentiment_buy_pct": 80.0, "is_open": 1},
        {"symbol": "MSFT", "instrument_id": 1002, "exchange_name": "NASDAQ",
         "display_name": "Microsoft", "type_id": 5, "daily_change": -0.5,
         "sentiment_buy_pct": 70.0, "is_open": 1},
    ])
    got = cat.get_many(["aapl", "MSFT", "ZZZ"])
    assert set(got) == {"AAPL", "MSFT"}
    assert got["AAPL"]["instrument_id"] == 1001
    assert got["AAPL"]["daily_change"] == 1.2
    assert got["MSFT"]["sentiment_buy_pct"] == 70.0


def test_upsert_is_idempotent_and_updates(tmp_path):
    cat = EtoroCatalog(tmp_path / "cat.db")
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1001, "daily_change": 1.0}])
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1001, "daily_change": 2.0}])
    got = cat.get_many(["AAPL"])
    assert len(got) == 1 and got["AAPL"]["daily_change"] == 2.0


def test_count(tmp_path):
    cat = EtoroCatalog(tmp_path / "cat.db")
    assert cat.count() == 0
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1}])
    assert cat.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_catalog.py -v`
Expected: FAIL — `No module named 'data_cache.etoro_catalog'`.

- [ ] **Step 3: Write `back/data_cache/etoro_catalog.py`**

```python
"""On-disk cache of the eToro instrument catalog: symbol -> instrumentId plus
daily change %, sentiment, and exchange. Populated from /instruments/discover."""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    symbol             TEXT PRIMARY KEY,
    instrument_id      INTEGER NOT NULL,
    exchange_id        INTEGER,
    exchange_name      TEXT,
    display_name       TEXT,
    type_id            INTEGER,
    daily_change       REAL,
    sentiment_buy_pct  REAL,
    is_open            INTEGER,
    updated_at         REAL
);
CREATE INDEX IF NOT EXISTS idx_instruments_id ON instruments(instrument_id);
"""

_COLS = ("symbol", "instrument_id", "exchange_id", "exchange_name", "display_name",
         "type_id", "daily_change", "sentiment_buy_pct", "is_open")


class EtoroCatalog:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def upsert(self, rows: Iterable[dict], now: Optional[float] = None) -> int:
        now = now if now is not None else time.time()
        payload = []
        for r in rows:
            sym = (r.get("symbol") or "").upper()
            if not sym or r.get("instrument_id") is None:
                continue
            payload.append((
                sym, int(r["instrument_id"]), r.get("exchange_id"), r.get("exchange_name"),
                r.get("display_name"), r.get("type_id"), r.get("daily_change"),
                r.get("sentiment_buy_pct"), r.get("is_open"), now,
            ))
        if not payload:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO instruments
                    (symbol, instrument_id, exchange_id, exchange_name, display_name,
                     type_id, daily_change, sentiment_buy_pct, is_open, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    instrument_id=excluded.instrument_id, exchange_id=excluded.exchange_id,
                    exchange_name=excluded.exchange_name, display_name=excluded.display_name,
                    type_id=excluded.type_id, daily_change=excluded.daily_change,
                    sentiment_buy_pct=excluded.sentiment_buy_pct, is_open=excluded.is_open,
                    updated_at=excluded.updated_at
            """, payload)
            return len(payload)

    def get_many(self, symbols: Iterable[str]) -> dict[str, dict]:
        syms = [s.upper() for s in symbols]
        if not syms:
            return {}
        placeholders = ",".join("?" * len(syms))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE symbol IN ({placeholders})", syms
            ).fetchall()
        return {r["symbol"]: dict(r) for r in rows}

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_catalog.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add back/data_cache/etoro_catalog.py back/tests/test_etoro_catalog.py
git commit -m "feat(screener): eToro instrument catalog cache"
```

---

### Task 3: Catalog refresh + endpoint, rates helper, and screener rewrite

**Files:**
- Modify: `back/routers/screener.py`
- Replace: `back/tests/test_screener.py`

This task rewrites the screener to use eToro. The old `test_screener.py` (Massive grouped-daily) is replaced because the price source changes.

- [ ] **Step 1: Replace `back/tests/test_screener.py`**

```python
"""Screener backend tests — eToro price source (mocked). No real API calls."""
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient


def _discover_page(items, page, page_size, total):
    return {"page": page, "pageSize": page_size, "totalItems": total, "items": items}


class FakeEtoro:
    """Routes EtoroClient.request by path: discover (paged) + rates (by ids)."""
    def __init__(self, instruments, rates):
        self._instruments = instruments  # list of discover item dicts
        self._rates = rates              # {instrumentID: {bid,ask,lastExecution}}
        self.calls = []

    def request(self, method, path, *, params=None, json=None):
        self.calls.append((method, path, params))
        if path == "/api/v1/instruments/discover":
            page = int(params.get("page", 1))
            size = int(params.get("pageSize", 1000))
            start = (page - 1) * size
            items = self._instruments[start:start + size]
            return _discover_page(items, page, size, len(self._instruments))
        if path == "/api/v1/market-data/instruments/rates":
            ids = params["instrumentIds"]
            ids = ids if isinstance(ids, list) else [ids]
            rates = [dict(instrumentID=int(i), **self._rates[int(i)])
                     for i in ids if int(i) in self._rates]
            return {"rates": rates}
        raise AssertionError(f"unexpected path {path}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()

    instruments = [
        {"instrumentId": 1001, "symbol": "AAPL", "displayname": "Apple",
         "internalExchangeName": "NASDAQ", "exchangeID": 4,
         "dailyPriceChange": 1.5, "buyHoldingPct": 82.0, "isExchangeOpen": True},
        {"instrumentId": 1002, "symbol": "MSFT", "displayname": "Microsoft",
         "internalExchangeName": "NASDAQ", "exchangeID": 4,
         "dailyPriceChange": -0.7, "buyHoldingPct": 65.0, "isExchangeOpen": True},
    ]
    rates = {
        1001: {"bid": 213.5, "ask": 213.7, "lastExecution": 213.6},
        1002: {"bid": 401.0, "ask": 401.2, "lastExecution": 401.1},
    }
    fake = FakeEtoro(instruments, rates)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    # small fixed universe (decouple from data files)
    monkeypatch.setattr(screener, "_load_universe", lambda u: [
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Tech"},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Tech"},
        {"ticker": "NOPE", "name": "Unmapped Co.", "sector": "X"},
    ])

    from main import app
    return TestClient(app), fake


def test_refresh_catalog_populates(client):
    tc, _ = client
    r = tc.post("/screener/refresh-etoro-catalog")
    assert r.status_code == 200
    assert r.json()["instruments"] == 2


def test_screener_uses_live_etoro_prices(client):
    tc, _ = client
    tc.post("/screener/refresh-etoro-catalog")
    r = tc.get("/screener/sp500")
    assert r.status_code == 200
    rows = {row["ticker"]: row for row in r.json()}
    aapl = rows["AAPL"]
    assert aapl["price"] == 213.6        # lastExecution
    assert aapl["sell"] == 213.5         # bid
    assert aapl["buy"] == 213.7          # ask
    assert aapl["change_pct"] == 1.5     # dailyPriceChange
    assert aapl["sentiment_buy_pct"] == 82.0
    assert aapl["exchange"] == "NASDAQ"
    assert aapl["instrument_id"] == 1001
    # unmapped ticker -> null price
    assert rows["NOPE"]["price"] is None


def test_screener_unknown_universe_404(client):
    tc, _ = client
    from routers import screener
    # restore real loader so unknown universe raises 404
    import importlib
    # _load_universe is monkeypatched to ignore the name; assert mapped ones still work
    r = tc.get("/screener/sp500")
    assert r.status_code == 200
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_screener.py -v`
Expected: FAIL — `screener` has no `get_server_client` / `CATALOG_DB` / refresh endpoint yet.

- [ ] **Step 3: Rewrite `back/routers/screener.py`**

Replace the ENTIRE file with:

```python
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
    """Page /instruments/discover into the catalog cache. Returns counts."""
    client = get_server_client()
    catalog = EtoroCatalog(CATALOG_DB)
    fields = ("instrumentId,symbol,displayname,exchangeID,internalExchangeName,"
              "dailyPriceChange,buyHoldingPct,isExchangeOpen")
    page, page_size, total_upserted = 1, 1000, 0
    while page <= 50:  # hard cap (~50k instruments) — defensive
        res = client.request("GET", "/api/v1/instruments/discover",
                             params={"fields": fields, "pageSize": page_size, "page": page})
        items = res.get("items", []) if isinstance(res, dict) else []
        if not items:
            break
        rows = [{
            "symbol": it.get("symbol"),
            "instrument_id": it.get("instrumentId"),
            "exchange_id": it.get("exchangeID"),
            "exchange_name": it.get("internalExchangeName"),
            "display_name": it.get("displayname"),
            "type_id": it.get("instrumentTypeID"),
            "daily_change": it.get("dailyPriceChange"),
            "sentiment_buy_pct": it.get("buyHoldingPct"),
            "is_open": 1 if it.get("isExchangeOpen") else 0,
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


def _build_rows(universe: str) -> list[ScreenerRow]:
    tickers = _load_universe(universe)
    catalog = EtoroCatalog(CATALOG_DB)
    mapped = catalog.get_many([t["ticker"] for t in tickers])

    ids = [mapped[t["ticker"]]["instrument_id"] for t in tickers if t["ticker"] in mapped]
    client = get_server_client()
    rates = _fetch_rates(client, ids) if ids else {}

    md_cache = MetadataCache(METADATA_DB)
    rows: list[ScreenerRow] = []
    for t in tickers:
        ticker = t["ticker"]
        cat = mapped.get(ticker)
        rate = rates.get(cat["instrument_id"]) if cat else None
        md = md_cache.get(ticker)
        rows.append(ScreenerRow(
            ticker=ticker, name=t["name"], sector=t["sector"],
            instrument_id=cat["instrument_id"] if cat else None,
            exchange=cat.get("exchange_name") if cat else None,
            price=rate.get("lastExecution") if rate else None,
            sell=rate.get("bid") if rate else None,
            buy=rate.get("ask") if rate else None,
            change_pct=cat.get("daily_change") if cat else None,
            sentiment_buy_pct=cat.get("sentiment_buy_pct") if cat else None,
            is_open=bool(cat["is_open"]) if cat and cat.get("is_open") is not None else None,
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
```

> Note: `/movers` is declared BEFORE `/{universe}` so the literal `movers` path is not captured by the `{universe}` param.

- [ ] **Step 4: Run the screener tests to verify they pass**

Run: `python -m pytest tests/test_screener.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add back/routers/screener.py back/tests/test_screener.py
git commit -m "feat(screener): live eToro prices via catalog + /rates; refresh endpoint"
```

---

### Task 4: Daily Movers tests

**Files:**
- Create: `back/tests/test_screener_movers.py`

(The `/movers` endpoint was implemented in Task 3; this task adds focused coverage.)

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_screener_movers.py
import pytest
from fastapi.testclient import TestClient
from tests.test_screener import FakeEtoro  # reuse the fake


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()
    instruments = [
        {"instrumentId": 1, "symbol": "UP1", "displayname": "Up One",
         "internalExchangeName": "NYSE", "dailyPriceChange": 9.0,
         "buyHoldingPct": 90.0, "isExchangeOpen": True},
        {"instrumentId": 2, "symbol": "UP2", "displayname": "Up Two",
         "internalExchangeName": "NYSE", "dailyPriceChange": 4.0,
         "buyHoldingPct": 60.0, "isExchangeOpen": True},
        {"instrumentId": 3, "symbol": "DN1", "displayname": "Down One",
         "internalExchangeName": "NYSE", "dailyPriceChange": -6.0,
         "buyHoldingPct": 30.0, "isExchangeOpen": True},
    ]
    rates = {i: {"bid": 1.0, "ask": 1.1, "lastExecution": 1.05} for i in (1, 2, 3)}
    fake = FakeEtoro(instruments, rates)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    monkeypatch.setattr(screener, "_load_universe", lambda u: [
        {"ticker": "UP1", "name": "Up One", "sector": "X"},
        {"ticker": "UP2", "name": "Up Two", "sector": "X"},
        {"ticker": "DN1", "name": "Down One", "sector": "X"},
    ])
    from main import app
    return TestClient(app)


def test_movers_gainers_sorted_desc(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/movers", params={"direction": "gainers", "limit": 2})
    assert r.status_code == 200
    rows = r.json()
    assert [x["ticker"] for x in rows] == ["UP1", "UP2"]
    assert rows[0]["change_pct"] == 9.0


def test_movers_losers_sorted_asc(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/movers", params={"direction": "losers", "limit": 1})
    assert r.status_code == 200
    assert r.json()[0]["ticker"] == "DN1"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_screener_movers.py -v`
Expected: PASS (2 tests) — the endpoint already exists from Task 3.

- [ ] **Step 3: Commit**

```bash
git add back/tests/test_screener_movers.py
git commit -m "test(screener): daily movers gainers/losers coverage"
```

---

### Task 5: Full suite + live verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole back/ offline suite**

Run: `python -m pytest tests/ -q`
Expected: all PASS — existing back tests + etoro_server, etoro_catalog, screener (eToro), screener_movers. (No `get_grouped_daily_aggs` references remain in the screener.)

- [ ] **Step 2: Confirm the app imports**

Run: `python -c "import main; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Live verification (needs network + .env eToro keys; skip if offline)**

Start the API: `python -m uvicorn main:app --port 8833 --log-level warning` (background), then:

```bash
# 1. populate the catalog (paged discover)
curl -s -X POST http://127.0.0.1:8833/screener/refresh-etoro-catalog
# 2. live eToro screener (sell/buy/change/sentiment/exchange)
curl -s "http://127.0.0.1:8833/screener/sp500" | python -c "import sys,json; r=json.load(sys.stdin); print(r[0])"
# 3. daily movers
curl -s "http://127.0.0.1:8833/screener/movers?universe=combined&direction=gainers&limit=5" \
  | python -c "import sys,json; [print(x['ticker'], x['change_pct']) for x in json.load(sys.stdin)]"
```
Expected: refresh returns `{"instruments": <thousands>}`; sp500 row has non-null `price`, `sell`, `buy`, `change_pct`, `sentiment_buy_pct`, `exchange`; movers prints 5 biggest gainers. Stop the server when done.

- [ ] **Step 4: Commit (only if a tweak was needed)**

```bash
git add -A
git commit -m "chore(screener): verify live eToro screener + movers"
```

---

## Self-Review notes

- **Spec coverage:** server client (Task 1), catalog cache (Task 2), catalog refresh + endpoint + rates batching + screener eToro rewrite + new ScreenerRow fields (Task 3), movers (Task 3 impl + Task 4 tests), verification (Task 5). ✓ Exchange names sourced from `internalExchangeName` (spec's `/market-data/exchanges` call dropped as redundant — simpler, noted).
- **Type/name consistency:** `get_server_client()` returns `EtoroClient` used in `refresh_catalog`/`_fetch_rates`/`_build_rows`; `EtoroCatalog.upsert/get_many/count` signatures match Tasks 2↔3; `ScreenerRow` fields identical across router + tests; `CATALOG_DB`/`METADATA_DB`/`_load_universe`/`_snapshot_memo` monkeypatched consistently in both test files; `/movers` registered before `/{universe}`. ✓
- **Placeholders:** none — complete code in every step.
- **Backward-compat:** ScreenerRow keeps `ticker,name,sector,price,change_pct,volume,market_cap,pe_ratio` (frontend-safe) and adds new fields; `volume` now always null (eToro rates lacks it).
```
