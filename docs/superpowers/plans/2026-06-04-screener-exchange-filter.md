# Screener exchange filter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user filter the screener's stocks (and any category) by **exchange** (Nasdaq, NYSE, LSE…) via a server-side filter + a dropdown, so the ~12k-instrument list stops being a jumble.

**Architecture:** The eToro catalog already stores `exchange_name`. Add an optional `exchange` filter to the catalog's `query`/`all_for_category`, plus an `exchanges(asset_class)` aggregate; expose a new `GET /screener/exchanges/{category}` and an `exchange` param on `/screener/category/{category}`. The React screener gains a per-category exchange dropdown wired into the existing server-side category fetch.

**Tech Stack:** Backend: FastAPI, SQLite, pytest (`TestClient`, offline `FakeEtoro`). Frontend: React + TanStack Query + Vitest + MSW.

Backend commands from `etoro/back/`; frontend from `etoro/front/`. Clean commits, **no** Co-Authored-By trailer. Repo branch `feat/yahoo-data-source` (controller syncs `main` after each task).

**Design source:** `docs/superpowers/specs/2026-06-04-screener-exchange-filter-design.md`.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/data_cache/etoro_catalog.py` | + `idx_instruments_exchange`; `exchange` param on `query`/`all_for_category`; new `exchanges(asset_class)` |
| `back/routers/screener.py` | + `exchange` query param on `/category/{category}`; new `GET /exchanges/{category}` |
| `back/tests/test_etoro_catalog.py` | + tests for `exchanges()` and exchange-filtered `query`/`all_for_category` |
| `back/tests/test_screener_category.py` | + tests for `?exchange=` and `/exchanges/{category}` |
| `front/src/types/screener.ts` | + `ExchangeOption` |
| `front/src/api/screener.ts` | + `exchange` in `CategoryParams`/`fetchCategory`; new `fetchExchanges` |
| `front/src/__tests__/handlers.ts` | + MSW handler for `/screener/exchanges/:category` |
| `front/src/hooks/useExchanges.ts` | new |
| `front/src/components/ExchangeFilter.tsx` | new dropdown |
| `front/src/App.tsx` | exchange state + wiring (reset page on change, reset exchange on category change) |
| `front/src/__tests__/*` | api + ExchangeFilter tests |

---

### Task 1: Catalog — `exchanges()` + exchange filter on query/all_for_category

**Files:**
- Modify: `back/data_cache/etoro_catalog.py`
- Test: `back/tests/test_etoro_catalog.py`

- [ ] **Step 1: Write the failing tests**

Append to `back/tests/test_etoro_catalog.py`:
```python
def test_exchanges_distinct_counts_sorted(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks", "exchange_name": "Nasdaq"},
        {"symbol": "MSFT", "instrument_id": 2, "asset_class": "Stocks", "exchange_name": "Nasdaq"},
        {"symbol": "JPM", "instrument_id": 3, "asset_class": "Stocks", "exchange_name": "NYSE"},
        {"symbol": "BTC", "instrument_id": 4, "asset_class": "Crypto", "exchange_name": "Digital Currency"},
        {"symbol": "NOEXCH", "instrument_id": 5, "asset_class": "Stocks", "exchange_name": None},
    ])
    ex = cat.exchanges("Stocks")
    assert ex == [{"exchange": "Nasdaq", "count": 2}, {"exchange": "NYSE", "count": 1}]
    # NULL exchange excluded; other asset_classes excluded
    assert cat.exchanges("Crypto") == [{"exchange": "Digital Currency", "count": 1}]


def test_query_and_all_for_category_exchange_filter(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks", "exchange_name": "Nasdaq",
         "display_name": "Apple"},
        {"symbol": "JPM", "instrument_id": 2, "asset_class": "Stocks", "exchange_name": "NYSE",
         "display_name": "JPMorgan"},
    ])
    rows, total = cat.query("Stocks", exchange="Nasdaq")
    assert total == 1 and [r["symbol"] for r in rows] == ["AAPL"]
    allrows = cat.all_for_category("Stocks", exchange="NYSE")
    assert [r["symbol"] for r in allrows] == ["JPM"]
    # no exchange → both
    _, total_all = cat.query("Stocks")
    assert total_all == 2
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_etoro_catalog.py -v -k "exchange"`
Expected: FAIL — `exchanges` not defined / `query` has no `exchange` kwarg.

- [ ] **Step 3: Edit `back/data_cache/etoro_catalog.py`**

Add the index to the `SCHEMA` string (after the existing `idx_instruments_asset` line, before the closing `"""`):
```python
CREATE INDEX IF NOT EXISTS idx_instruments_exchange ON instruments(exchange_name);
```

Change the `query` signature and WHERE-building. Replace:
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
```
with:
```python
    def query(self, asset_class: str, q: Optional[str] = None, sort: str = "name",
              page: int = 1, page_size: int = 50,
              exchange: Optional[str] = None) -> tuple[list[dict], int]:
        """Return (rows, total) for one asset_class, optionally text-filtered (symbol or
        display_name contains q) and exchange-filtered, sorted by display_name ('name')
        or symbol, paginated."""
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        where = "asset_class = ?"
        params: list = [asset_class]
        if q:
            where += " AND (UPPER(symbol) LIKE ? OR UPPER(display_name) LIKE ?)"
            like = f"%{q.upper()}%"
            params += [like, like]
        if exchange:
            where += " AND exchange_name = ?"
            params.append(exchange)
```

Change `all_for_category`. Replace:
```python
    def all_for_category(self, asset_class: str, q: Optional[str] = None) -> list[dict]:
        """All rows for one asset_class (no pagination), optional text filter on
        symbol/display_name. For in-memory sort by computed live fields."""
        where = "asset_class = ?"
        params: list = [asset_class]
        if q:
            where += " AND (UPPER(symbol) LIKE ? OR UPPER(display_name) LIKE ?)"
            like = f"%{q.upper()}%"
            params += [like, like]
```
with:
```python
    def all_for_category(self, asset_class: str, q: Optional[str] = None,
                         exchange: Optional[str] = None) -> list[dict]:
        """All rows for one asset_class (no pagination), optional text + exchange filter.
        For in-memory sort by computed live fields."""
        where = "asset_class = ?"
        params: list = [asset_class]
        if q:
            where += " AND (UPPER(symbol) LIKE ? OR UPPER(display_name) LIKE ?)"
            like = f"%{q.upper()}%"
            params += [like, like]
        if exchange:
            where += " AND exchange_name = ?"
            params.append(exchange)
```

Add the `exchanges` method (after `all_for_category`, at end of class):
```python
    def exchanges(self, asset_class: str) -> list[dict]:
        """Distinct exchanges for one asset_class with instrument counts, busiest first.
        Skips NULL/empty exchange names. Return: [{"exchange": str, "count": int}, ...]."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT exchange_name AS exchange, COUNT(*) AS count FROM instruments "
                "WHERE asset_class = ? AND exchange_name IS NOT NULL AND exchange_name <> '' "
                "GROUP BY exchange_name ORDER BY count DESC, exchange_name",
                (asset_class,),
            ).fetchall()
        return [dict(r) for r in rows]
```
NOTE: existing DBs created before this change won't have `idx_instruments_exchange`, but `CREATE INDEX IF NOT EXISTS` runs in `__init__` via `executescript(SCHEMA)`, so the index is added on next open. No data migration needed (column already exists).

- [ ] **Step 4: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_etoro_catalog.py -v` → all PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add back/data_cache/etoro_catalog.py back/tests/test_etoro_catalog.py
git commit -m "feat(catalog): exchange filter on query/all_for_category + exchanges() aggregate"
```

---

### Task 2: Screener router — `exchange` param + `/exchanges/{category}`

**Files:**
- Modify: `back/routers/screener.py`
- Test: `back/tests/test_screener_category.py`

- [ ] **Step 1: Write the failing tests**

Append to `back/tests/test_screener_category.py` (the module already has a `client` fixture that seeds AAPL+MSFT on `Nasdaq` and BTC+ABT on `Digital Currency`, and calls `POST /screener/refresh-etoro-catalog` to populate the catalog):
```python
def test_exchanges_endpoint_lists_distinct_with_counts(client):
    client.post("/screener/refresh-etoro-catalog")
    r = client.get("/screener/exchanges/stocks")
    assert r.status_code == 200
    assert r.json() == [{"exchange": "Nasdaq", "count": 2}]
    assert client.get("/screener/exchanges/crypto").json() == [
        {"exchange": "Digital Currency", "count": 2}]


def test_exchanges_unknown_category_404(client):
    assert client.get("/screener/exchanges/widgets").status_code == 404


def test_category_exchange_filter(client):
    client.post("/screener/refresh-etoro-catalog")
    hit = client.get("/screener/category/stocks?exchange=Nasdaq&sort=name")
    assert hit.status_code == 200 and hit.json()["total"] == 2
    miss = client.get("/screener/category/stocks?exchange=NYSE&sort=name")
    assert miss.json()["total"] == 0 and miss.json()["items"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_screener_category.py -v -k "exchange"`
Expected: FAIL — no `/exchanges/...` route; `exchange` param ignored (NYSE returns 2, not 0).

- [ ] **Step 3: Edit `back/routers/screener.py`**

(a) Add the `exchange` param to `category_browse` and thread it through. Change the signature:
```python
@router.get("/category/{category}", response_model=CategoryPage)
def category_browse(category: str, page: int = Query(1), pageSize: int = Query(50),
                    sort: str = Query("change"), dir: str = Query("desc"),
                    q: Optional[str] = Query(None)):
```
to:
```python
@router.get("/category/{category}", response_model=CategoryPage)
def category_browse(category: str, page: int = Query(1), pageSize: int = Query(50),
                    sort: str = Query("change"), dir: str = Query("desc"),
                    q: Optional[str] = Query(None), exchange: Optional[str] = Query(None)):
```
Change the `sort == "name"` branch call:
```python
        rows, total = catalog.query(asset, q, "name", page, page_size)
```
to:
```python
        rows, total = catalog.query(asset, q, "name", page, page_size, exchange=exchange)
```
Change the change/price branch call:
```python
    all_rows = catalog.all_for_category(asset, q)
```
to:
```python
    all_rows = catalog.all_for_category(asset, q, exchange=exchange)
```

(b) Add the `/exchanges/{category}` route. Place it immediately **before** the `@router.get("/{universe}", ...)` route (so the literal path is matched first). Insert:
```python
@router.get("/exchanges/{category}")
def category_exchanges(category: str):
    asset = _CATEGORY_MAP.get(category.lower())
    if asset is None:
        raise HTTPException(404, f"Unknown category: {category}")
    return EtoroCatalog(CATALOG_DB).exchanges(asset)
```

- [ ] **Step 4: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_screener_category.py -v` → all PASS.
Then full backend suite: `python -m pytest tests/ -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add back/routers/screener.py back/tests/test_screener_category.py
git commit -m "feat(screener): exchange query param + GET /screener/exchanges/{category}"
```

---

### Task 3: Frontend types + API + MSW handler

**Files:**
- Modify: `front/src/types/screener.ts`, `front/src/api/screener.ts`, `front/src/__tests__/handlers.ts`
- Test: `front/src/__tests__/screenerApi.test.ts` (extend)

- [ ] **Step 1: Add the failing API test**

Append to `front/src/__tests__/screenerApi.test.ts`:
```typescript
import { fetchExchanges } from "../api/screener";

describe("fetchExchanges", () => {
  it("returns exchange options for a category", async () => {
    const ex = await fetchExchanges("stocks");
    expect(Array.isArray(ex)).toBe(true);
    expect(ex[0]).toHaveProperty("exchange");
    expect(ex[0]).toHaveProperty("count");
  });
});

describe("fetchCategory exchange param", () => {
  it("includes exchange in the querystring when set", async () => {
    const page = await fetchCategory("stocks", { exchange: "Nasdaq" });
    expect(page.category).toBe("stocks");
  });
});
```
(The file already imports `fetchCategory`; if the import line is `import { fetchCategory, fetchCatalogStatus } from "../api/screener";`, add `fetchExchanges` there instead of a second import to avoid duplicate-import lint — read the file first and match its existing import.)

- [ ] **Step 2: Add the MSW handlers**

In `front/src/__tests__/handlers.ts`, add these two handlers to the `handlers` array (place them BEFORE the catch-all `http.get("/screener/:bad", ...)` handler so they take precedence):
```typescript
  http.get("/screener/exchanges/:category", () =>
    HttpResponse.json([
      { exchange: "Nasdaq", count: 3706 },
      { exchange: "NYSE", count: 2341 },
    ])),
```
Also extend the existing `http.get("/screener/category/:category", ...)` handler so it echoes the `exchange` param into the response (so a test can assert it was forwarded) — change its `return HttpResponse.json({ ... })` to include `exchange`:
```typescript
    return HttpResponse.json({
      items, total: 2, page: Number(url.searchParams.get("page") ?? 1),
      pageSize: Number(url.searchParams.get("pageSize") ?? 50), category,
      exchange: url.searchParams.get("exchange"),
    });
```
(Adding an extra field to the JSON is harmless for existing tests, which only read `items/total/page/category`.)

- [ ] **Step 3: Run to verify it fails**

Run (from `front/`): `npm run test:run -- screenerApi`
Expected: FAIL — `fetchExchanges` not exported.

- [ ] **Step 4: Edit `front/src/types/screener.ts`**

Append:
```typescript
export interface ExchangeOption {
  exchange: string;
  count: number;
}
```

- [ ] **Step 5: Edit `front/src/api/screener.ts`**

Add `exchange` to `CategoryParams`:
```typescript
export interface CategoryParams {
  page?: number;
  pageSize?: number;
  sort?: SortKey;
  dir?: "asc" | "desc";
  q?: string;
  exchange?: string;
}
```
In `fetchCategory`, after the `if (params.q) qs.set("q", params.q);` line, add:
```typescript
  if (params.exchange) qs.set("exchange", params.exchange);
```
Add the import of `ExchangeOption` to the top type import, and a new function. Change the import line:
```typescript
import type {
  ScreenerRow, Universe, Category, CategoryPage, CatalogStatus, SortKey,
} from "../types/screener";
```
to:
```typescript
import type {
  ScreenerRow, Universe, Category, CategoryPage, CatalogStatus, SortKey, ExchangeOption,
} from "../types/screener";
```
Append the function:
```typescript
export async function fetchExchanges(category: Category): Promise<ExchangeOption[]> {
  const resp = await fetch(`/screener/exchanges/${category}`);
  if (!resp.ok) throw new Error(`Exchanges fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}
```

- [ ] **Step 6: Run to verify it passes**

Run (from `front/`): `npm run test:run -- screenerApi` → PASS. Then full suite `npm run test:run` → all pass.

- [ ] **Step 7: Commit**

```bash
git add front/src/types/screener.ts front/src/api/screener.ts front/src/__tests__/handlers.ts front/src/__tests__/screenerApi.test.ts
git commit -m "feat(front): fetchExchanges + exchange param + ExchangeOption type"
```

---

### Task 4: `useExchanges` hook + `ExchangeFilter` dropdown

**Files:**
- Create: `front/src/hooks/useExchanges.ts`, `front/src/components/ExchangeFilter.tsx`, `front/src/__tests__/ExchangeFilter.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/ExchangeFilter.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExchangeFilter } from "../components/ExchangeFilter";
import type { ExchangeOption } from "../types/screener";

const options: ExchangeOption[] = [
  { exchange: "Nasdaq", count: 3706 },
  { exchange: "NYSE", count: 2341 },
];

describe("ExchangeFilter", () => {
  it("renders All + options and fires onChange with the picked exchange", async () => {
    const onChange = vi.fn();
    render(<ExchangeFilter value={null} options={options} onChange={onChange} />);
    expect(screen.getByRole("option", { name: /All exchanges/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Nasdaq (3706)" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox"), "Nasdaq");
    expect(onChange).toHaveBeenCalledWith("Nasdaq");
  });

  it("emits null when All is selected", async () => {
    const onChange = vi.fn();
    render(<ExchangeFilter value="Nasdaq" options={options} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "__all__");
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- ExchangeFilter`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the hook and component**

`front/src/hooks/useExchanges.ts`:
```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchExchanges } from "../api/screener";
import type { Category } from "../types/screener";

export function useExchanges(category: Category) {
  return useQuery({
    queryKey: ["screener", "exchanges", category],
    queryFn: () => fetchExchanges(category),
    staleTime: 300_000,
  });
}
```

`front/src/components/ExchangeFilter.tsx` (styled to match the existing toolbar `<select>`/sort control — dark tokens bg-bg-surface / border-border-default / text-fg-default; `__all__` sentinel maps to `null`):
```tsx
import type { ExchangeOption } from "../types/screener";

interface Props {
  value: string | null;
  options: ExchangeOption[];
  onChange: (exchange: string | null) => void;
}

const ALL = "__all__";

export function ExchangeFilter({ value, options, onChange }: Props) {
  return (
    <label className="inline-flex items-center gap-2 text-xs text-fg-muted">
      <span className="hidden sm:inline">Exchange</span>
      <select
        value={value ?? ALL}
        disabled={options.length <= 1}
        onChange={(e) => onChange(e.target.value === ALL ? null : e.target.value)}
        className="rounded-md border border-border-default bg-bg-surface px-2 py-1.5 text-sm text-fg-default outline-none transition-colors focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/40 disabled:opacity-50"
      >
        <option value={ALL}>All exchanges</option>
        {options.map((o) => (
          <option key={o.exchange} value={o.exchange}>
            {o.exchange} ({o.count})
          </option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- ExchangeFilter` → PASS (2).

- [ ] **Step 5: Commit**

```bash
git add front/src/hooks/useExchanges.ts front/src/components/ExchangeFilter.tsx front/src/__tests__/ExchangeFilter.test.tsx
git commit -m "feat(front): useExchanges hook + ExchangeFilter dropdown"
```

---

### Task 5: Wire `App` + full verify

**Files:**
- Modify: `front/src/App.tsx`
- Test: existing `front/src/__tests__/App.test.tsx` (must stay green)

- [ ] **Step 1: Wire `front/src/App.tsx`**

(a) Add imports (next to the other hook/component imports):
```tsx
import { useExchanges } from "./hooks/useExchanges";
import { ExchangeFilter } from "./components/ExchangeFilter";
```
(b) Add exchange state — after `const [sort, setSort] = useState<SortKey>("change");`:
```tsx
  const [exchange, setExchange] = useState<string | null>(null);
```
(c) Pass `exchange` into the category fetch — change the `useCategoryData(...)` call:
```tsx
  const { data, isLoading, isError, isFetching, refetch } = useCategoryData(
    category,
    { page, pageSize: PAGE_SIZE, sort, dir: "desc", q: q || undefined },
  );
```
to:
```tsx
  const { data, isLoading, isError, isFetching, refetch } = useCategoryData(
    category,
    { page, pageSize: PAGE_SIZE, sort, dir: "desc", q: q || undefined, exchange: exchange ?? undefined },
  );
```
(d) Load exchanges for the current category — after the `status` useQuery block:
```tsx
  const exchanges = useExchanges(category);
```
(e) Reset exchange when the category changes — change the existing `onCategory`:
```tsx
  const onCategory = useCallback((c: Category) => {
    setCategory(c);
    setPage(1);
  }, []);
```
to:
```tsx
  const onCategory = useCallback((c: Category) => {
    setCategory(c);
    setExchange(null);
    setPage(1);
  }, []);
```
(f) Add the exchange change handler — next to `onSort`:
```tsx
  const onExchange = useCallback((ex: string | null) => {
    setExchange(ex);
    setPage(1);
  }, []);
```
(g) Render the filter in the toolbar — the toolbar's first row currently is:
```tsx
          <div className="flex flex-wrap items-center gap-3 py-3">
            <CategoryTabs value={category} onChange={onCategory} />

            <label className="ml-auto inline-flex items-center gap-2 text-xs text-fg-muted">
```
Insert the `ExchangeFilter` between `CategoryTabs` and the sort `<label>` (so tabs sit left, exchange next, sort pushed right by its `ml-auto`):
```tsx
          <div className="flex flex-wrap items-center gap-3 py-3">
            <CategoryTabs value={category} onChange={onCategory} />

            <ExchangeFilter
              value={exchange}
              options={exchanges.data ?? []}
              onChange={onExchange}
            />

            <label className="ml-auto inline-flex items-center gap-2 text-xs text-fg-muted">
```

- [ ] **Step 2: Run the App test + full suite**

Run (from `front/`): `npm run test:run` → all PASS (App test asserts tabs + a Bitcoin row; the MSW `/screener/exchanges/:category` handler now serves the dropdown, so mounting `useExchanges` doesn't error). Then `npm run build` (`tsc -b && vite build`) → clean, no type errors.

- [ ] **Step 3: Live verify (backend on 8765 + curl)**

Backend (from `back/`): `python -m uvicorn main:app --reload --port 8765`.
```bash
curl -s "http://127.0.0.1:8765/screener/exchanges/stocks" | python -c "import sys,json;d=json.load(sys.stdin);print('exchanges',len(d));[print(' ',x['exchange'],x['count']) for x in d[:5]]"
curl -s "http://127.0.0.1:8765/screener/category/stocks?exchange=Nasdaq&pageSize=3&sort=name" | python -c "import sys,json;d=json.load(sys.stdin);print('total',d['total']);[print(' ',x['ticker'],x['exchange']) for x in d['items']]"
```
Expected: the exchanges list shows Nasdaq/NYSE/… with counts; the filtered category returns only `Nasdaq` rows and a `total` matching the Nasdaq count (≈3706). Frontend (`cd front && npm run dev`): the Exchange dropdown appears in the toolbar, picking "Nasdaq (3706)" narrows the table, switching category resets it to "All exchanges". (Skip the GUI step if no display; the curls confirm the backend half.)

- [ ] **Step 4: Commit**

```bash
git add front/src/App.tsx
git commit -m "feat(front): wire exchange filter into screener toolbar"
```

---

## Self-Review notes

- **Spec coverage:** catalog `exchanges()` + exchange filter (Task 1) ↔ spec "Backend — EtoroCatalog"; `exchange` param + `/exchanges/{category}` (Task 2) ↔ "Backend — routers/screener.py"; types/api/MSW (Task 3) ↔ "Frontend types/api"; `useExchanges` + `ExchangeFilter` (Task 4) ↔ "hooks/components"; App wiring + reset-on-category + reset-page + live verify (Task 5) ↔ "App.tsx" + "Data flow". Filter applied before pagination/sort (catalog WHERE) → correct `total`. "All"=null sentinel; disabled when ≤1 option. ✓
- **Type/name consistency:** `exchanges(asset_class) -> [{exchange,count}]` shape consistent across catalog (Task 1), endpoint (Task 2), MSW (Task 3), `ExchangeOption` (Task 3), `ExchangeFilter` props (Task 4). `CategoryParams.exchange` (Task 3) consumed by `fetchCategory` querystring + `useCategoryData` + App (Task 5). `query(..., exchange=)` / `all_for_category(..., exchange=)` kwargs match call sites in Task 2. ✓
- **Placeholders:** none. **Deps:** none new. **Backward-compat:** `exchange` is optional everywhere — omitting it preserves current behaviour; existing category/WS/movers/universe untouched. **Ports:** backend 8765. **Sector:** explicitly out of scope (separate spec).
```
