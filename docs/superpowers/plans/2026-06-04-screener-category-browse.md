# Screener category browse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /screener/category/{category}` so all six eToro categories (stocks/crypto/etf/indices/commodities/currencies) are browsable separately with live prices, pagination, sort, and text search.

**Architecture:** `EtoroCatalog` gains a `query(asset_class, q, sort, page, page_size)` method (DB-level filter/sort/paginate, new index). The screener adds a category endpoint that maps the category to an eToro asset class, reads the catalog, enriches with live price (`current_rate`/`/rates`) and computed change% (`/closing-price`), and returns a paginated wrapper.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite, pytest. Reuses the eToro catalog + `_fetch_rates`/`_fetch_closing` helpers already in `back/routers/screener.py`.

All commands assume cwd `etoro/back/`. Tests offline (eToro mocked via the existing `FakeEtoro` in `tests/test_screener.py`). Clean commits, **no** Co-Authored-By trailer.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/data_cache/etoro_catalog.py` | + `query(...)` method + `asset_class` index |
| `back/routers/screener.py` | + `_CATEGORY_MAP`, `CategoryPage`, `_category_rows`, `GET /category/{category}` |
| `back/tests/test_etoro_catalog.py` | + query tests |
| `back/tests/test_screener_category.py` | new |

---

### Task 1: `EtoroCatalog.query` + asset_class index

**Files:**
- Modify: `back/data_cache/etoro_catalog.py`
- Test: `back/tests/test_etoro_catalog.py`

- [ ] **Step 1: Add failing tests**

Append to `back/tests/test_etoro_catalog.py`:

```python
def test_query_filters_by_asset_class_and_paginates(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": f"S{i}", "instrument_id": i, "asset_class": "Stocks",
                 "display_name": f"Stock {i}"} for i in range(1, 6)]
               + [{"symbol": "BTC", "instrument_id": 100, "asset_class": "Crypto",
                   "display_name": "Bitcoin"}])
    rows, total = cat.query("Stocks", page=1, page_size=2)
    assert total == 5 and len(rows) == 2
    rows2, total2 = cat.query("Crypto")
    assert total2 == 1 and rows2[0]["symbol"] == "BTC"


def test_query_text_filter(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks", "display_name": "Apple"},
                {"symbol": "MSFT", "instrument_id": 2, "asset_class": "Stocks", "display_name": "Microsoft"}])
    rows, total = cat.query("Stocks", q="apple")
    assert total == 1 and rows[0]["symbol"] == "AAPL"


def test_query_name_sort(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": "Z", "instrument_id": 1, "asset_class": "Stocks", "display_name": "Zeta"},
                {"symbol": "A", "instrument_id": 2, "asset_class": "Stocks", "display_name": "Alpha"}])
    rows, _ = cat.query("Stocks", sort="name")
    assert [r["display_name"] for r in rows] == ["Alpha", "Zeta"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_etoro_catalog.py -k query -v`
Expected: FAIL — `EtoroCatalog` has no `query`.

- [ ] **Step 3: Add the index + `query` to `back/data_cache/etoro_catalog.py`**

In `SCHEMA`, add an asset_class index after the existing index line:
```python
CREATE INDEX IF NOT EXISTS idx_instruments_id ON instruments(instrument_id);
CREATE INDEX IF NOT EXISTS idx_instruments_asset ON instruments(asset_class);
```

Add this method to the `EtoroCatalog` class (after `count`):
```python
    def query(self, asset_class: str, q: Optional[str] = None, sort: str = "name",
              page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        """Return (rows, total) for one asset_class, optionally text-filtered (symbol or
        display_name contains q), sorted by display_name ('name') or symbol, paginated."""
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        where = "asset_class = ?"
        params: list = [asset_class]
        if q:
            where += " AND (UPPER(symbol) LIKE ? OR UPPER(display_name) LIKE ?)"
            like = f"%{q.upper()}%"
            params += [like, like]
        order = "display_name" if sort == "name" else "symbol"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM instruments WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE {where} ORDER BY {order} "
                f"LIMIT ? OFFSET ?", params + [page_size, (page - 1) * page_size]).fetchall()
        return [dict(r) for r in rows], total
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_etoro_catalog.py -v`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add back/data_cache/etoro_catalog.py back/tests/test_etoro_catalog.py
git commit -m "feat(screener): EtoroCatalog.query (filter/sort/paginate by category)"
```

---

### Task 2: Category browse endpoint

**Files:**
- Modify: `back/routers/screener.py`
- Test: `back/tests/test_screener_category.py`

- [ ] **Step 1: Write the failing test**

Create `back/tests/test_screener_category.py`:

```python
import pytest
from fastapi.testclient import TestClient
from tests.test_screener import FakeEtoro


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import screener
    screener._snapshot_memo.clear()
    instruments = [
        {"instrumentId": 1001, "symbol": "AAPL", "displayName": "Apple",
         "assetClass": "Stocks", "exchangeName": "Nasdaq", "currentRate": 210.0},
        {"instrumentId": 1002, "symbol": "MSFT", "displayName": "Microsoft",
         "assetClass": "Stocks", "exchangeName": "Nasdaq", "currentRate": 400.0},
        {"instrumentId": 100000, "symbol": "BTC", "displayName": "Bitcoin",
         "assetClass": "Crypto", "exchangeName": "Digital Currency", "currentRate": 65000.0},
        {"instrumentId": 9000, "symbol": "ABT", "displayName": "Arcblock",
         "assetClass": "Crypto", "exchangeName": "Digital Currency", "currentRate": 0.2},
    ]
    rates = {100000: {"bid": 64990.0, "ask": 65010.0, "lastExecution": 65000.0}}
    closing = {1001: {"officialClosingPrice": 200.0, "isMarketOpen": True},   # +5%
               1002: {"officialClosingPrice": 410.0, "isMarketOpen": True},   # -2.4%
               100000: {"officialClosingPrice": 60000.0, "isMarketOpen": True},  # +8.3%
               9000: {"officialClosingPrice": 0.25, "isMarketOpen": True}}    # -20%
    fake = FakeEtoro(instruments, rates, closing)
    monkeypatch.setattr(screener, "get_server_client", lambda: fake)
    monkeypatch.setattr(screener, "CATALOG_DB", tmp_path / "cat.db")
    monkeypatch.setattr(screener, "METADATA_DB", tmp_path / "meta.db")
    from main import app
    return TestClient(app)


def test_category_unknown_404(client):
    client.post("/screener/refresh-etoro-catalog")
    assert client.get("/screener/category/widgets").status_code == 404


def test_category_stocks_wrapper_and_filter(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/category/stocks")
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "stocks" and body["total"] == 2
    assert body["page"] == 1 and body["pageSize"] == 50
    syms = {x["ticker"] for x in body["items"]}
    assert syms == {"AAPL", "MSFT"}


def test_category_crypto_includes_collision_symbol(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/crypto").json()
    syms = {x["ticker"] for x in body["items"]}
    assert syms == {"BTC", "ABT"}            # ABT shows correctly under Crypto
    btc = next(x for x in body["items"] if x["ticker"] == "BTC")
    assert btc["price"] == 65000.0 and btc["sell"] == 64990.0 and btc["buy"] == 65010.0
    assert round(btc["change_pct"], 1) == 8.3


def test_category_sort_change_desc(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/crypto",
                      params={"sort": "change", "dir": "desc"}).json()
    # BTC +8.3% before ABT -20%
    assert [x["ticker"] for x in body["items"]] == ["BTC", "ABT"]


def test_category_text_search(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/stocks", params={"q": "apple"}).json()
    assert body["total"] == 1 and body["items"][0]["ticker"] == "AAPL"


def test_category_pagesize_clamped(client):
    client.post("/screener/refresh-etoro-catalog")
    body = client.get("/screener/category/stocks", params={"pageSize": 9999}).json()
    assert body["pageSize"] == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_screener_category.py -v`
Expected: FAIL — no `/category/{category}` route.

- [ ] **Step 3: Edit `back/routers/screener.py`**

(a) Add near the other module constants (after `RATES_BATCH = 100`):
```python
_CATEGORY_MAP = {
    "stocks": "Stocks", "crypto": "Crypto", "etf": "ETF",
    "indices": "Indices", "commodities": "Commodity", "currencies": "Forex",
}
```

(b) Add the `CategoryPage` model right after the `ScreenerRow` class:
```python
class CategoryPage(BaseModel):
    items: list[ScreenerRow]
    total: int
    page: int
    pageSize: int
    category: str
```

(c) Add the row-builder + route. Place the route DEFINITION **before** the `@router.get("/{universe}")` route (so the literal `category` segment is unambiguous). Insert this block immediately above the `@router.get("/{universe}", ...)` definition:
```python
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

    # sort by change or price: load all (for this category+q), compute, sort, paginate,
    # then add live bid/ask for the visible page only.
    all_rows, total = catalog.query(asset, q, "name", 1, 100_000)
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
```

> The `/category/{category}` route is registered before `/{universe}`, so `GET /screener/category/crypto` resolves here (and even without ordering, it is 2 path segments vs the 1-segment `/{universe}`, so no capture).

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_screener_category.py -v`
Expected: PASS (6 tests).
Then full suite: `python -m pytest tests/ -q` → all pass. `python -c "import main; print('ok')"` → ok.

- [ ] **Step 5: Commit**

```bash
git add back/routers/screener.py back/tests/test_screener_category.py
git commit -m "feat(screener): GET /category/{category} browse (paginated, sort, search)"
```

---

### Task 3: Full suite + live verification

**Files:** none (verification only)

- [ ] **Step 1: Full offline suite**

Run: `python -m pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 2: Live verification (network + Docker not needed; eToro .env keys + the catalog DB needed)**

Delete the stale catalog DB so the schema (with the new index) is recreated, then start the API:
```bash
rm -f ~/.etoro/etoro_catalog.db
python -m uvicorn main:app --port 8890 --log-level warning   # background
```
Then:
```bash
curl -s -X POST http://127.0.0.1:8890/screener/refresh-etoro-catalog
# crypto tab, biggest movers
curl -s "http://127.0.0.1:8890/screener/category/crypto?sort=change&dir=desc&pageSize=5" \
  | python -c "import sys,json; d=json.load(sys.stdin); print('total',d['total']); [print(' ',x['ticker'],x['price'],round(x['change_pct'],2) if x['change_pct'] is not None else None,x['exchange']) for x in d['items']]"
# stocks text search
curl -s "http://127.0.0.1:8890/screener/category/stocks?q=apple&pageSize=3" \
  | python -c "import sys,json; d=json.load(sys.stdin); print('total',d['total']); [print(' ',x['ticker'],x['name'],x['price']) for x in d['items']]"
# each category returns a non-empty page
for c in stocks crypto etf indices commodities currencies; do
  echo -n "$c -> "; curl -s "http://127.0.0.1:8890/screener/category/$c?pageSize=1" | python -c "import sys,json; print('total', json.load(sys.stdin)['total'])"
done
```
Expected: crypto movers sorted by change with prices + exchange "Digital Currency"; `q=apple` returns Apple; every category prints a positive total. Stop the server when done.

- [ ] **Step 3: Commit (only if a tweak was needed)**

```bash
git add -A
git commit -m "chore(screener): verify category browse end-to-end"
```

---

## Self-Review notes

- **Spec coverage:** `EtoroCatalog.query` + index (Task 1); `_CATEGORY_MAP`, `CategoryPage`, `_category_rows`/`_enrich_category`, `GET /category/{category}` with pagination/sort/search/clamp/404 (Task 2); all six categories via the map; collision symbols (ABT) correct under Crypto (Task 2 test); live verification across all categories (Task 3). ✓
- **Type/name consistency:** `EtoroCatalog.query(asset_class, q, sort, page, page_size) -> (rows, total)` used identically in tests + endpoint; `_enrich_category(rows, client, closing, with_rates)` reused for both sort paths; `CategoryPage(items, total, page, pageSize, category)` returned consistently; reuses existing `_fetch_rates`/`_fetch_closing`/`ScreenerRow`/`get_server_client`/`EtoroCatalog`/`CATALOG_DB`. ✓
- **Placeholders:** none. **Route order:** `/category/{category}` before `/{universe}` (and segment-count-distinct anyway). **Backward-compat:** no change to `/screener/{universe}` or `/movers`.
```
