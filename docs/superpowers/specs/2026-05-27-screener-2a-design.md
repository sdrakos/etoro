# Screener Sub-phase 2A — Foundation Design

**Status:** Design approved 2026-05-27
**Owner:** sdrakos
**Scope:** The first slice of the TradingView-style Screener UI. Single Overview tab, 500-stock universe (S&P 500), 8 columns. Foundation for sub-phases 2B-2E (extra tabs, advanced filters, watchlist sidebar) — none of which are in this spec.

## Context

`etoro/back/` is a FastAPI wrapper over the Massive.com (Polygon.io rebrand) market data API (104 endpoints, shipped as Phase 0). `etoro/trader/` is the Python backtest framework (Phase 1, shipped). `etoro/front/` is currently empty — Sub-phase 2A is the first real frontend.

The end-state vision (from `p_debug/p1.png`) is a TradingView-style screener with 10 tabs (Overview, Performance, Extended Hours, Valuation, Dividends, Profitability, Income Statement, Balance Sheet, Cash Flow, Technicals) covering 200+ filterable columns, a watchlist sidebar, and saved filter sets. That is months of work. This spec decomposes that vision into 5 sub-phases:

| # | Sub-phase | What it adds |
|---|---|---|
| **2A** | **Foundation** (this spec) | React app + table + sort + search + Overview tab (8 cols) |
| 2B | Tab system | Performance + Technicals tabs |
| 2C | Fundamentals tabs | Valuation, Profitability, Income, Balance Sheet, Cash Flow, Dividends |
| 2D | Advanced filter bar | TradingView-style top bar with multi-filters + save sets |
| 2E | Watchlist sidebar | Add/remove tickers, live mini-prices |

## Goals

1. Ship a working screener UI that loads ~500 S&P 500 stocks and renders 8 columns: ticker, name, sector, price, change %, volume, market cap, P/E ratio.
2. Sort by any column (asc/desc).
3. Search by ticker or name (client-side, debounced, case-insensitive substring).
4. Dark theme matching TradingView aesthetic.
5. Data refresh: auto every 60s + manual button, single backend call per refresh.
6. End-to-end testable (backend pytest + frontend Vitest + one Playwright happy-path).

## Non-goals

- Additional tabs (2B+) — Overview only.
- Advanced filter bar (2D) — search box only.
- Watchlist sidebar (2E) — not rendered.
- Per-row drill-down / detail pages.
- Per-user saved layouts.
- Mobile responsive design (desktop-first, breakpoints later).
- Multi-asset support (forex/crypto/options) — equities only.
- Real-time streaming via WebSocket — polling 60s is fine for Phase 2A.

## Architecture

### Directory layout

```
etoro/
├── back/                                  (existing — extended)
│   ├── routers/
│   │   └── screener.py                    NEW: GET /screener/sp500
│   ├── data/                              NEW directory
│   │   ├── sp500.json                     curated S&P 500 list
│   │   └── metadata_cache.py              SQLite cache for slow-changing fields
│   ├── main.py                            (modified: include screener router)
│   └── tests/
│       └── test_screener.py               NEW
└── front/                                 NEW (currently empty)
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── index.html
    ├── .eslintrc.json
    ├── src/
    │   ├── main.tsx                       entry — mounts <App/>
    │   ├── App.tsx                        shell — header + screener
    │   ├── api/
    │   │   └── screener.ts                typed fetch wrapper
    │   ├── components/
    │   │   ├── ScreenerTable.tsx          Tanstack Table
    │   │   ├── SearchBox.tsx
    │   │   └── ColumnHeader.tsx
    │   ├── hooks/
    │   │   └── useScreenerData.ts         React Query wrapper
    │   ├── types/
    │   │   └── screener.ts                ScreenerRow interface
    │   ├── lib/
    │   │   └── formatters.ts              $5.21T, +1.42%, etc.
    │   └── styles/
    │       └── index.css                  Tailwind directives
    ├── src/__tests__/
    │   ├── ScreenerTable.test.tsx
    │   ├── SearchBox.test.tsx
    │   ├── formatters.test.tsx
    │   └── useScreenerData.test.tsx
    └── e2e/
        └── screener.spec.ts               Playwright happy-path
```

### Tech stack

| Layer | Choice | Why |
|---|---|---|
| Bundler | Vite | Fast dev server, modern, simple |
| Language | TypeScript | Type safety for table data shapes |
| UI library | React 18 | Largest ecosystem for financial tables |
| Table | Tanstack Table v8 (headless) | Sort/filter primitives, we own the styling |
| Server state | Tanstack Query (React Query) | Caching + auto-refetch + retry |
| Styling | Tailwind CSS | Utility-first, no component lock-in |
| Backend additions | FastAPI (existing) + SQLite (new metadata cache) | Reuse existing stack |
| Unit testing | Vitest + React Testing Library + MSW | Fast, integrates with Vite |
| E2E | Playwright | Single happy-path |

No router (single page for 2A). No state management library (React Query covers server state; component-local `useState` covers UI).

### Backend additions

**`back/data/sp500.json`** — static curated list:

```json
{
  "as_of": "2026-05-27",
  "tickers": [
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
    {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Technology"},
    ...
  ]
}
```

500 entries with ticker + name + sector. Refresh quarterly via a manual script (out of scope for 2A — initial seed is sufficient).

**`back/data/metadata_cache.py`** — SQLite store:

```sql
CREATE TABLE screener_metadata (
    ticker     TEXT PRIMARY KEY,
    market_cap REAL,
    pe_ratio   REAL,
    updated_at INTEGER          -- Unix milliseconds
);
```

TTL: 24 hours. On query, stale rows are refreshed by calling `get_ticker_details(ticker)` + `list_ratios(ticker)`. Cache lives at `~/.etoro/screener_metadata.db`.

**`back/routers/screener.py`** — single endpoint:

```python
@router.get("/sp500")
def sp500_screener(client = Depends(get_client)):
    """
    1. Load S&P 500 list from sp500.json (cached in-memory)
    2. Call get_snapshot_all('stocks') → returns ALL US stocks current state (1 API call)
    3. Filter snapshots to S&P 500 set
    4. Join with metadata_cache (refresh stale rows)
    5. Return list[ScreenerRow]
    """
```

Response shape (Pydantic-validated):

```python
class ScreenerRow(BaseModel):
    ticker: str
    name: str
    sector: str
    price: float | None        # null if snapshot missing
    change_pct: float | None
    volume: float | None
    market_cap: float | None
    pe_ratio: float | None
```

`null` is permitted on price/change_pct/volume so a missing snapshot does not break the entire response. Frontend renders `—` for nulls.

### Frontend layout

```
┌──────────────────────────────────────────────┐
│ etoro · Screener                  Phase 2A   │   header
├──────────────────────────────────────────────┤
│ 🔍 Search ticker or name…        [Refresh]  │   SearchBox + manual refresh
├──────────────────────────────────────────────┤
│ Ticker│Name      │Sector│Price │Chg%│Vol│   │   ScreenerTable (sticky header)
├──────┼──────────┼──────┼──────┼────┼───┤   │
│ NVDA │NVIDIA    │Tech  │215.33│+1.4│169M│   │   ~500 rows, no virtualization
│ ...                                          │
└──────────────────────────────────────────────┘
```

**Colour palette** (dark theme, TradingView-inspired):

| Token | Hex | Use |
|---|---|---|
| `bg-base` | `#0f0f0f` | page background |
| `bg-surface` | `#1a1a1a` | table rows alt |
| `fg-default` | `#d1d4dc` | text |
| `fg-muted` | `#787b86` | placeholders, headers |
| `accent-blue` | `#2962ff` | links |
| `accent-green` | `#26a69a` | positive change |
| `accent-red` | `#ef5350` | negative change |

Configured in `tailwind.config.js` under `theme.extend.colors`.

**`types/screener.ts`**:

```typescript
export interface ScreenerRow {
  ticker: string;
  name: string;
  sector: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
}
```

**Formatters (`lib/formatters.ts`)**:

- `formatMoney(n)` → `$5.21T` / `$453.2B` / `$1.2M` / `$42.50`
- `formatPercent(n)` → `+1.42%` / `-3.18%`
- `formatVolume(n)` → `169M` / `1.2B`
- `formatPE(n)` → fixed 1 decimal or `—` if null

### Data flow

**First load:**

1. User opens `localhost:5173`.
2. `useScreenerData()` fires `GET http://localhost:8765/screener/sp500`.
3. Backend reads `sp500.json` (memoised in-process), calls `snapshot_all('stocks')` once, filters to the S&P 500 set, joins with metadata cache, returns ~500 rows.
4. Frontend renders the table.
5. Search filters in-memory (no roundtrip). Column-header clicks sort in-memory.

**Refresh behaviour:**

- React Query config: `staleTime: 60_000`, `refetchInterval: 60_000`, `refetchOnWindowFocus: true`.
- Manual `[Refresh]` button calls `queryClient.invalidateQueries(['screener', 'sp500'])`.
- Refresh is a single GET; backend uses the metadata cache to avoid 500 N+1 calls.

**Free-tier rate budget**: one `snapshot_all` call per refresh = 1 call/min. Metadata refresh runs only for rows with stale (>24h) entries — first cold start may incur up to 500 sequential calls but is spread across runs and only happens once.

### Error handling

| Failure | Backend response | Frontend behaviour |
|---|---|---|
| Massive 401 (bad key) | 500 `{"error": "API key invalid"}` | Toast: "Backend auth error — check back/.env" |
| Massive 429 (rate limited) | 502 + retry-after | React Query auto-retries 3× with backoff |
| Empty response | 200 `[]` | Empty state: "No data — try Refresh" |
| Network down (front) | — | React Query retries; UI shows last cached data + stale indicator |
| Pydantic validation failure on a row | row omitted, others returned | Log on server; user sees N-1 rows silently |

## Testing

### Backend (pytest)

`back/tests/test_screener.py`:

- `test_sp500_endpoint_returns_rows` — fixture `sp500.json` with 3 tickers + mock SDK → endpoint returns 3 `ScreenerRow` dicts matching schema.
- `test_metadata_cache_within_ttl_no_extra_calls` — second request inside 24h → 0 extra `get_ticker_details` calls.
- `test_metadata_cache_stale_triggers_refresh` — backdate `updated_at` to >24h ago → next request refreshes those rows.
- `test_missing_snapshot_returns_nulls` — ticker exists in `sp500.json` but absent from `snapshot_all` → row has `price=None`, no exception.
- `test_response_validates_against_pydantic_schema` — full response parses cleanly via `ScreenerRow.model_validate`.

Coverage target: `back/routers/screener.py` + `back/data/metadata_cache.py` ≥ 80%.

### Frontend (Vitest + RTL + MSW)

`front/src/__tests__/`:

- `ScreenerTable.test.tsx` — render 3 mock rows → all 8 columns × 3 rows in DOM.
- `ScreenerTable.test.tsx` — click "Price" header → rows sort ascending; click again → descending.
- `SearchBox.test.tsx` — type "NVDA" → `onFilter` callback fires after 200ms debounce with `"NVDA"`.
- `formatters.test.tsx` — `formatMoney(5_210_000_000_000) === '$5.21T'`; negative percent gets `text-red` class.
- `useScreenerData.test.tsx` — MSW intercepts `/screener/sp500`; verifies loading → success → error states.

Coverage target: `ScreenerTable.tsx` + `SearchBox.tsx` + `formatters.ts` ≥ 70%. `App.tsx` not measured (composition shell).

### E2E (Playwright)

`front/e2e/screener.spec.ts`:

1. Start `back/` dev server on 8765 + `front/` dev server on 5173 (via `package.json` script that uses `concurrently`).
2. Visit `http://localhost:5173`.
3. Assert: table has > 100 rows.
4. Type "AAPL" in search → at most 5 rows visible.
5. Click "Price" header → rows reorder.

One test, no parallelisation. Skipped in CI for now (manual run).

## Open questions / future work

- **Persistence of column widths / sort state**: out of scope — will revisit with 2D filter persistence.
- **S&P 500 list maintenance**: a refresh script that scrapes Wikipedia or pulls from a paid index source is a 2A.1 follow-up. Not blocking for 2A ship.
- **CORS**: `back/main.py` already has `allow_origins=["*"]`. Tighten to `localhost:5173` only after 2A ships.
- **Dev-server orchestration**: `front/package.json` will have `"dev": "vite"` and `"dev:full": "concurrently 'uvicorn back.main:app --reload' 'vite'"`. Decide which is the canonical entry in CLAUDE.md after first run.

## Dependencies

**Backend (additions to existing requirements.txt):**

```
# already present: fastapi, uvicorn, polygon-api-client, python-dotenv, pydantic
# no new deps for 2A
```

**Frontend (`front/package.json`):**

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-table": "^8.20.0",
    "@tanstack/react-query": "^5.50.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "typescript": "^5.5.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "msw": "^2.3.0",
    "@playwright/test": "^1.46.0",
    "jsdom": "^25.0.0",
    "concurrently": "^9.0.0"
  }
}
```

## Success criteria

Sub-phase 2A is done when:

1. `cd back && uvicorn main:app` running on :8765 serves `GET /screener/sp500` returning ≥ 400 valid `ScreenerRow` JSON entries.
2. `cd front && npm run dev` on :5173 renders the table with the rows.
3. Sorting by any column works; search filters rows live; manual refresh button updates data.
4. All backend tests pass with coverage ≥ 80% on new files.
5. All frontend Vitest tests pass with coverage ≥ 70% on new files.
6. Playwright happy-path passes locally.
7. README updated to mark Sub-phase 2A shipped.
