# eToro-style screener frontend + near-live prices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the screener UI look like eToro (category tabs + Change/Sell/Buy/Sentiment/Exchange columns) with non-frozen prices, by adding a backend catalog auto-refresh and rebuilding the React frontend against the category endpoints.

**Architecture:** A FastAPI lifespan background task refreshes the eToro catalog every ~90s so `current_rate` stays fresh; a `catalog-status` endpoint exposes freshness. The React app (`front/`) switches from universe-based to category-based: tabs → `GET /screener/category/{category}` with server-side pagination/sort/search, polled every 30s. True WebSocket real-time is a future spec.

**Tech Stack:** Backend: FastAPI, asyncio, pytest. Frontend: React + Vite + TanStack Query + TanStack Table + Tailwind + Vitest + MSW + Playwright.

Backend commands from `etoro/back/`; frontend from `etoro/front/`. Clean commits, **no** Co-Authored-By trailer.

> **DESIGN MANDATE (user requirement): the most professional, beautiful screener possible.**
> For the **frontend visual tasks (4, 5, 6)** the implementer MUST invoke the `frontend-design` skill FIRST and follow it: a cohesive design system (refined dark palette, type scale, spacing rhythm), polished data-dense tables (sticky header, zebra/hover, right-aligned tabular-nums numerics, color-coded change, sentiment bars, market-open status, exchange chips), tasteful micro-interactions (tab/sort transitions, skeleton loaders, subtle row hover), responsive layout, and accessibility (focus states, aria). The component code blocks below are a FUNCTIONAL baseline (data wiring + test contracts) — keep the props/test assertions, but **elevate the markup/styling to a top-tier, eToro-grade look** per the frontend-design skill. Don't ship the plain baseline as-is.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/routers/screener.py` | + `_refresh_once`, `CATALOG_REFRESH_S`, `_last_refresh_ts`, `GET /catalog-status` |
| `back/main.py` | + lifespan that runs the refresh loop |
| `back/tests/test_screener_status.py` | new |
| `front/src/types/screener.ts` | + `Category`, `CATEGORIES`, extended `ScreenerRow`, `CategoryPage` |
| `front/src/api/screener.ts` | + `fetchCategory`, `fetchCatalogStatus` |
| `front/src/__tests__/handlers.ts` | + MSW handlers for category + status |
| `front/src/hooks/useCategoryData.ts` | new (replaces useScreenerData in App) |
| `front/src/components/CategoryTabs.tsx` | new |
| `front/src/components/Pagination.tsx` | new |
| `front/src/components/ScreenerTable.tsx` | new columns (Change/Sell/Buy/Sentiment/Exchange) |
| `front/src/App.tsx` | tabs + server search + pagination + sort + status |
| `front/src/__tests__/*` + `front/e2e/screener.spec.ts` | tests |

---

### Task 1: Backend catalog auto-refresh + status endpoint

**Files:**
- Modify: `back/routers/screener.py`, `back/main.py`
- Test: `back/tests/test_screener_status.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_screener_status.py
import time
from fastapi.testclient import TestClient


def test_refresh_once_sets_timestamp(monkeypatch):
    from routers import screener
    monkeypatch.setattr(screener, "refresh_catalog", lambda: {"instruments": 7})
    screener._last_refresh_ts = None
    result = screener._refresh_once()
    assert result == {"instruments": 7}
    assert screener._last_refresh_ts is not None


def test_catalog_status_endpoint(tmp_path, monkeypatch):
    from routers import screener
    from data_cache.etoro_catalog import EtoroCatalog
    db = tmp_path / "cat.db"
    EtoroCatalog(db).upsert([{"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks"}])
    monkeypatch.setattr(screener, "CATALOG_DB", db)
    screener._last_refresh_ts = time.time() - 5
    from main import app
    tc = TestClient(app)
    r = tc.get("/screener/catalog-status")
    assert r.status_code == 200
    body = r.json()
    assert body["instruments"] == 1
    assert 4 <= body["last_refresh_age_s"] <= 30
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_screener_status.py -v`
Expected: FAIL — `screener` has no `_refresh_once` / `/catalog-status`.

- [ ] **Step 3: Edit `back/routers/screener.py`**

Add after the existing constants (e.g. after `RATES_BATCH = 100`):
```python
CATALOG_REFRESH_S = 90
_last_refresh_ts: Optional[float] = None
```
Add a testable single-refresh helper + status route. Put the route **before** the `@router.get("/{universe}")` route (so `catalog-status` is not captured as a universe). Insert next to the `/movers` route:
```python
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
```
(`time` is already imported in screener.py.)

- [ ] **Step 4: Edit `back/main.py` — add the lifespan refresh loop**

Add imports at the top (after the existing imports):
```python
import asyncio
from contextlib import asynccontextmanager
from routers.screener import _refresh_once, CATALOG_REFRESH_S
```
Add the lifespan **above** the `app = FastAPI(...)` line:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _loop():
        while True:
            try:
                await asyncio.to_thread(_refresh_once)
            except Exception:
                pass  # never let a refresh failure kill the loop
            await asyncio.sleep(CATALOG_REFRESH_S)
    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
```
Change the `app = FastAPI(` call to pass `lifespan=lifespan` (add the kwarg, keep title/description/version):
```python
app = FastAPI(
    title="Massive Market Data API",
    description="Wrapper over Massive.com (Polygon.io rebrand) — stocks, options, indices, crypto, forex, economy, filings, news.",
    version="1.0.0",
    lifespan=lifespan,
)
```

- [ ] **Step 5: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_screener_status.py -v` → PASS (2).
Then full suite: `python -m pytest tests/ -q` → all pass. `python -c "import main; print('ok')"` → ok.

- [ ] **Step 6: Commit**

```bash
git add back/routers/screener.py back/main.py back/tests/test_screener_status.py
git commit -m "feat(screener): catalog auto-refresh loop + /catalog-status"
```

---

### Task 2: Frontend types + API + MSW handlers

**Files:**
- Modify: `front/src/types/screener.ts`, `front/src/api/screener.ts`, `front/src/__tests__/handlers.ts`
- Test: `front/src/__tests__/screenerApi.test.ts` (create)

- [ ] **Step 1: Extend `front/src/types/screener.ts`**

Append (keep the existing `Universe`/`UNIVERSES`/`ScreenerRow`):
```typescript
export type Category =
  | "stocks" | "crypto" | "etf" | "indices" | "commodities" | "currencies";

export const CATEGORIES: { id: Category; label: string }[] = [
  { id: "stocks", label: "Stocks" },
  { id: "crypto", label: "Crypto" },
  { id: "etf", label: "ETFs" },
  { id: "indices", label: "Indices" },
  { id: "commodities", label: "Commodities" },
  { id: "currencies", label: "Currencies" },
];

export type SortKey = "change" | "name" | "price";

export interface CategoryRow extends ScreenerRow {
  instrument_id: number | null;
  exchange: string | null;
  sell: number | null;
  buy: number | null;
  sentiment_buy_pct: number | null;
  is_open: boolean | null;
}

export interface CategoryPage {
  items: CategoryRow[];
  total: number;
  page: number;
  pageSize: number;
  category: string;
}

export interface CatalogStatus {
  instruments: number;
  last_refresh_age_s: number | null;
}
```

- [ ] **Step 2: Write the failing API test**

Create `front/src/__tests__/screenerApi.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { fetchCategory, fetchCatalogStatus } from "../api/screener";

describe("fetchCategory", () => {
  it("requests the category with params and returns a page", async () => {
    const page = await fetchCategory("crypto", { page: 1, pageSize: 50, sort: "change", dir: "desc" });
    expect(page.category).toBe("crypto");
    expect(page.total).toBeGreaterThan(0);
    expect(page.items[0]).toHaveProperty("sell");
    expect(page.items[0]).toHaveProperty("buy");
  });
});

describe("fetchCatalogStatus", () => {
  it("returns instrument count + age", async () => {
    const s = await fetchCatalogStatus();
    expect(typeof s.instruments).toBe("number");
  });
});
```

- [ ] **Step 3: Add MSW handlers in `front/src/__tests__/handlers.ts`**

Add these handlers to the exported `handlers` array (keep the existing `/screener/:universe` handler). Use the project's existing msw import style (`http`, `HttpResponse` from `msw`):
```typescript
  http.get("/screener/category/:category", ({ params, request }) => {
    const url = new URL(request.url);
    const category = String(params.category);
    const items = [
      { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
        exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010,
        change_pct: 8.3, sentiment_buy_pct: 90, is_open: true,
        volume: null, market_cap: null, pe_ratio: null },
      { ticker: "ABT", name: "Arcblock", sector: "Crypto", instrument_id: 9000,
        exchange: "Digital Currency", price: 0.2, sell: null, buy: null,
        change_pct: -20, sentiment_buy_pct: 30, is_open: true,
        volume: null, market_cap: null, pe_ratio: null },
    ];
    return HttpResponse.json({
      items, total: 2, page: Number(url.searchParams.get("page") ?? 1),
      pageSize: Number(url.searchParams.get("pageSize") ?? 50), category,
    });
  }),
  http.get("/screener/catalog-status", () =>
    HttpResponse.json({ instruments: 15000, last_refresh_age_s: 12 })),
```
(If the file imports `rest` from older msw instead of `http`, match that style — read the file first and follow its existing pattern.)

- [ ] **Step 4: Rewrite `front/src/api/screener.ts`**

Replace its contents (keep `fetchScreener` for the legacy universe endpoint; add the new functions):
```typescript
import type {
  ScreenerRow, Universe, Category, CategoryPage, CatalogStatus, SortKey,
} from "../types/screener";

export async function fetchScreener(universe: Universe): Promise<ScreenerRow[]> {
  const resp = await fetch(`/screener/${universe}`);
  if (!resp.ok) throw new Error(`Screener fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}

export interface CategoryParams {
  page?: number;
  pageSize?: number;
  sort?: SortKey;
  dir?: "asc" | "desc";
  q?: string;
}

export async function fetchCategory(
  category: Category, params: CategoryParams = {},
): Promise<CategoryPage> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page ?? 1));
  qs.set("pageSize", String(params.pageSize ?? 50));
  qs.set("sort", params.sort ?? "change");
  qs.set("dir", params.dir ?? "desc");
  if (params.q) qs.set("q", params.q);
  const resp = await fetch(`/screener/category/${category}?${qs.toString()}`);
  if (!resp.ok) throw new Error(`Category fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function fetchCatalogStatus(): Promise<CatalogStatus> {
  const resp = await fetch(`/screener/catalog-status`);
  if (!resp.ok) throw new Error(`Status fetch failed: ${resp.status}`);
  return resp.json();
}
```

- [ ] **Step 5: Run the API test**

Run (from `front/`): `npm run test:run -- screenerApi`
Expected: PASS (2).

- [ ] **Step 6: Commit**

```bash
git add front/src/types/screener.ts front/src/api/screener.ts front/src/__tests__/handlers.ts front/src/__tests__/screenerApi.test.ts
git commit -m "feat(front): category + catalog-status API + types"
```

---

### Task 3: `useCategoryData` hook

**Files:**
- Create: `front/src/hooks/useCategoryData.ts`, `front/src/__tests__/useCategoryData.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/useCategoryData.test.tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { useCategoryData } from "../hooks/useCategoryData";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useCategoryData", () => {
  it("fetches a category page", async () => {
    const { result } = renderHook(
      () => useCategoryData("crypto", { page: 1, pageSize: 50, sort: "change", dir: "desc" }),
      { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.category).toBe("crypto");
    expect(result.current.data?.items.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run → fails**

Run (from `front/`): `npm run test:run -- useCategoryData`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `front/src/hooks/useCategoryData.ts`**

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchCategory, type CategoryParams } from "../api/screener";
import type { Category } from "../types/screener";

export function useCategoryData(category: Category, params: CategoryParams) {
  return useQuery({
    queryKey: ["screener", "category", category, params],
    queryFn: () => fetchCategory(category, params),
    refetchInterval: 30_000,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}
```

- [ ] **Step 4: Run → passes**

Run (from `front/`): `npm run test:run -- useCategoryData`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front/src/hooks/useCategoryData.ts front/src/__tests__/useCategoryData.test.tsx
git commit -m "feat(front): useCategoryData polling hook"
```

---

### Task 4: CategoryTabs + Pagination components

**Files:**
- Create: `front/src/components/CategoryTabs.tsx`, `front/src/components/Pagination.tsx`
- Test: `front/src/__tests__/CategoryTabs.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/CategoryTabs.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CategoryTabs } from "../components/CategoryTabs";

describe("CategoryTabs", () => {
  it("renders all six categories and fires onChange", async () => {
    const onChange = vi.fn();
    render(<CategoryTabs value="stocks" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Stocks" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crypto" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Crypto" }));
    expect(onChange).toHaveBeenCalledWith("crypto");
  });
});
```

- [ ] **Step 2: Run → fails**

Run (from `front/`): `npm run test:run -- CategoryTabs`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the components**

`front/src/components/CategoryTabs.tsx`:
```tsx
import { CATEGORIES, type Category } from "../types/screener";

interface Props {
  value: Category;
  onChange: (c: Category) => void;
}

export function CategoryTabs({ value, onChange }: Props) {
  return (
    <div className="inline-flex rounded-md border border-border-default overflow-hidden">
      {CATEGORIES.map(({ id, label }) => {
        const active = id === value;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            aria-pressed={active}
            className={[
              "px-4 py-1.5 text-sm font-medium transition-colors",
              active ? "bg-accent-blue text-white"
                     : "bg-bg-surface text-fg-default hover:bg-bg-hover",
            ].join(" ")}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
```

`front/src/components/Pagination.tsx`:
```tsx
interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}

export function Pagination({ page, pageSize, total, onPage }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center gap-3 text-sm text-fg-muted">
      <button
        type="button"
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
        className="px-2 py-1 border border-border-default rounded disabled:opacity-40"
      >
        ‹ Prev
      </button>
      <span>Page {page} / {pages} · {total} items</span>
      <button
        type="button"
        onClick={() => onPage(page + 1)}
        disabled={page >= pages}
        className="px-2 py-1 border border-border-default rounded disabled:opacity-40"
      >
        Next ›
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run → passes**

Run (from `front/`): `npm run test:run -- CategoryTabs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front/src/components/CategoryTabs.tsx front/src/components/Pagination.tsx front/src/__tests__/CategoryTabs.test.tsx
git commit -m "feat(front): CategoryTabs + Pagination components"
```

---

### Task 5: ScreenerTable — eToro columns

**Files:**
- Modify: `front/src/components/ScreenerTable.tsx`
- Test: `front/src/__tests__/ScreenerTable.test.tsx` (replace)

- [ ] **Step 1: Replace `front/src/__tests__/ScreenerTable.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScreenerTable } from "../components/ScreenerTable";
import type { CategoryRow } from "../types/screener";

const rows: CategoryRow[] = [
  { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
    exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010,
    change_pct: 8.3, sentiment_buy_pct: 90, is_open: true,
    volume: null, market_cap: null, pe_ratio: null },
];

describe("ScreenerTable (eToro columns)", () => {
  it("renders Change/Sell/Buy/Sentiment/Exchange", () => {
    render(<ScreenerTable rows={rows} />);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("Bitcoin")).toBeInTheDocument();
    expect(screen.getByText("Digital Currency")).toBeInTheDocument();
    expect(screen.getByText("+8.30%")).toBeInTheDocument();
    expect(screen.getByText("64990.00")).toBeInTheDocument();  // sell
    expect(screen.getByText("65010.00")).toBeInTheDocument();  // buy
    expect(screen.getByText(/90/)).toBeInTheDocument();        // sentiment
  });
});
```

- [ ] **Step 2: Run → fails**

Run (from `front/`): `npm run test:run -- ScreenerTable`
Expected: FAIL (old table has no sell/buy/exchange columns; expects `filter` prop).

- [ ] **Step 3: Rewrite `front/src/components/ScreenerTable.tsx`**

```tsx
import type { CategoryRow } from "../types/screener";
import { formatPercent, changeColorClass } from "../lib/formatters";

interface Props {
  rows: CategoryRow[];
}

function num(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}

export function ScreenerTable({ rows }: Props) {
  return (
    <div className="overflow-auto h-full">
      <table className="w-full text-sm">
        <thead className="text-left text-fg-muted border-b border-border-default sticky top-0 bg-bg-base">
          <tr>
            <th className="py-2 pr-4">Market</th>
            <th className="py-2 pr-4">Change %</th>
            <th className="py-2 pr-4">Sell</th>
            <th className="py-2 pr-4">Buy</th>
            <th className="py-2 pr-4">Sentiment</th>
            <th className="py-2 pr-4">Exchange</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.instrument_id ?? r.ticker}`} className="border-b border-border-default/50 hover:bg-bg-hover">
              <td className="py-2 pr-4">
                <span className="inline-flex items-center gap-2">
                  <span className={["inline-block w-2 h-2 rounded-full",
                    r.is_open ? "bg-accent-green" : "bg-fg-muted"].join(" ")} />
                  <span className="font-mono font-medium">{r.ticker}</span>
                  <span className="text-fg-muted">{r.name}</span>
                </span>
              </td>
              <td className={["py-2 pr-4", changeColorClass(r.change_pct)].join(" ")}>
                {formatPercent(r.change_pct)}
              </td>
              <td className="py-2 pr-4">{num(r.sell)}</td>
              <td className="py-2 pr-4">{num(r.buy)}</td>
              <td className="py-2 pr-4">
                {r.sentiment_buy_pct === null ? "—" : (
                  <span className="inline-flex items-center gap-2">
                    <span className="inline-block h-1.5 w-16 rounded bg-bg-surface overflow-hidden">
                      <span className="block h-full bg-accent-green"
                        style={{ width: `${Math.max(0, Math.min(100, r.sentiment_buy_pct))}%` }} />
                    </span>
                    <span className="text-fg-muted text-xs">{Math.round(r.sentiment_buy_pct)}%</span>
                  </span>
                )}
              </td>
              <td className="py-2 pr-4 text-fg-muted">{r.exchange ?? "—"}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={6} className="py-6 text-center text-fg-muted">No instruments.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Run → passes**

Run (from `front/`): `npm run test:run -- ScreenerTable`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front/src/components/ScreenerTable.tsx front/src/__tests__/ScreenerTable.test.tsx
git commit -m "feat(front): eToro-style ScreenerTable columns (change/sell/buy/sentiment/exchange)"
```

---

### Task 6: App.tsx — tabs + server search + pagination + sort + status

**Files:**
- Modify: `front/src/App.tsx`
- Test: `front/src/__tests__/App.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/App.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
}

describe("App", () => {
  it("shows category tabs and loads a page", async () => {
    renderApp();
    expect(screen.getByRole("button", { name: "Crypto" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeInTheDocument());
  });

  it("switches category on tab click", async () => {
    renderApp();
    await userEvent.click(screen.getByRole("button", { name: "Crypto" }));
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run → fails**

Run (from `front/`): `npm run test:run -- App`
Expected: FAIL — App still renders the universe UI (no Crypto tab / Bitcoin).

- [ ] **Step 3: Rewrite `front/src/App.tsx`**

```tsx
import { useState } from "react";
import { useCategoryData } from "./hooks/useCategoryData";
import { useQuery } from "@tanstack/react-query";
import { fetchCatalogStatus } from "./api/screener";
import { CategoryTabs } from "./components/CategoryTabs";
import { SearchBox } from "./components/SearchBox";
import { ScreenerTable } from "./components/ScreenerTable";
import { Pagination } from "./components/Pagination";
import type { Category, SortKey } from "./types/screener";

const PAGE_SIZE = 50;

export default function App() {
  const [category, setCategory] = useState<Category>("stocks");
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("change");

  const { data, isLoading, isError, isFetching, refetch } = useCategoryData(
    category, { page, pageSize: PAGE_SIZE, sort, dir: "desc", q: q || undefined });
  const status = useQuery({ queryKey: ["catalog-status"], queryFn: fetchCatalogStatus,
    refetchInterval: 30_000 });

  const onCategory = (c: Category) => { setCategory(c); setPage(1); };
  const onSearch = (s: string) => { setQ(s); setPage(1); };

  return (
    <div className="min-h-screen flex flex-col bg-bg-base text-fg-default">
      <header className="px-6 py-4 border-b border-border-default flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">
          etoro <span className="text-fg-muted text-base font-normal">· Screener</span>
        </h1>
        <span className="text-xs text-fg-muted">
          {status.data ? `live · updated ${Math.round(status.data.last_refresh_age_s ?? 0)}s ago`
                       : "live"}
        </span>
      </header>

      <div className="px-6 py-3 border-b border-border-default flex items-center gap-4 flex-wrap">
        <CategoryTabs value={category} onChange={onCategory} />
        <select
          value={sort}
          onChange={(e) => { setSort(e.target.value as SortKey); setPage(1); }}
          className="bg-bg-surface border border-border-default rounded-md px-2 py-1.5 text-sm"
        >
          <option value="change">Sort: Change %</option>
          <option value="name">Sort: Name</option>
          <option value="price">Sort: Price</option>
        </select>
      </div>

      <div className="px-6 py-3 border-b border-border-default flex items-center gap-3">
        <SearchBox onSearch={onSearch} />
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="px-3 py-1.5 text-sm bg-bg-surface border border-border-default rounded-md hover:bg-bg-hover disabled:opacity-50"
        >
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
        {data && (
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
        )}
      </div>

      <main className="flex-1 p-6 overflow-hidden">
        {isLoading && <p className="text-fg-muted">Loading market data…</p>}
        {isError && (
          <div className="text-accent-red">
            Could not load data. Is the backend running on :8765?
          </div>
        )}
        {data && <ScreenerTable rows={data.items} />}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Run → passes**

Run (from `front/`): `npm run test:run -- App`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add front/src/App.tsx front/src/__tests__/App.test.tsx
git commit -m "feat(front): category-tabbed eToro screener (search/sort/pagination/status)"
```

---

### Task 7: Full frontend tests + typecheck + e2e + live verify

**Files:**
- Modify: `front/e2e/screener.spec.ts` (if it asserts the old universe UI)

- [ ] **Step 1: Run the full vitest suite + typecheck/build**

Run (from `front/`): `npm run test:run`
Expected: all PASS (the old `useScreenerData` test still passes — that hook is unchanged; if a now-removed component test fails, update it to the new UI). Then `npm run build` (tsc + vite) → succeeds with no type errors.

- [ ] **Step 2: Update the e2e happy-path to the category UI**

Read `front/e2e/screener.spec.ts`. If it drives the old universe selector / columns, update its selectors to: click a category tab (e.g. `getByRole("button", { name: "Crypto" })`), assert a row renders, type in search, assert pagination control is present. Keep it a happy-path. (Exact selectors per the new `App.tsx`/`ScreenerTable.tsx` above.)

- [ ] **Step 3: Live verify (backend on 8765 + frontend dev)**

Backend (from `back/`): `python -m uvicorn main:app --reload --port 8765` — the lifespan auto-refresh starts populating the catalog (first cycle ~60s).
Confirm freshness:
```bash
curl -s http://127.0.0.1:8765/screener/catalog-status
curl -s "http://127.0.0.1:8765/screener/category/crypto?sort=change&pageSize=5" | python -c "import sys,json;d=json.load(sys.stdin);print('total',d['total']);[print(' ',x['ticker'],x['price'],x['sell'],x['buy'],x['change_pct'],x['exchange']) for x in d['items']]"
```
Frontend (from `front/`): `npm run dev` → open the URL → category tabs switch, prices show Sell/Buy/Change/Sentiment/Exchange, "updated Xs ago" ticks, prices change after a refresh cycle (not frozen). (Skip if no GUI; the curl + status confirm the backend half.)

- [ ] **Step 4: Commit (if e2e or tweaks changed)**

```bash
git add -A
git commit -m "test(front): e2e + verify category screener end-to-end"
```

---

## Self-Review notes

- **Spec coverage:** backend auto-refresh loop + `/catalog-status` (Task 1); frontend types/api/MSW (Task 2); polling hook (Task 3); CategoryTabs + Pagination (Task 4); eToro columns table (Task 5); App tabs/search/sort/pagination/status (Task 6); full tests + e2e + live verify (Task 7). WebSocket explicitly deferred per spec. ✓
- **Type/name consistency:** `Category`, `CategoryRow`, `CategoryPage`, `CatalogStatus`, `SortKey` defined in Task 2 and used in Tasks 3–6; `fetchCategory(category, params)` / `fetchCatalogStatus()` signatures consistent across api + hook + App; `_refresh_once`/`CATALOG_REFRESH_S` defined in Task 1 backend and imported in main.py; `/catalog-status` route declared before `/{universe}`. ✓
- **Placeholders:** none. **Ports:** backend must run on 8765 (vite proxy). **Backward-compat:** `/screener/{universe}` + `fetchScreener` left intact; `useScreenerData` untouched (its test still green).
```
