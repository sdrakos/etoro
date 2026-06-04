# Portfolio view + live P&L — Implementation Plan (WS Spec 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Portfolio view that lists the demo account's open positions with P&L updating tick-by-tick from the existing `/ws/prices` relay, plus a per-position Close action.

**Architecture:** A new server-client backend router normalizes eToro positions + enriches them from the catalog; the React app gains a top-level «Screener | Portfolio» nav, and the Portfolio view computes P&L client-side from positions (REST) overlaid with live ticks (existing `usePriceStream`). Close uses the eToro market-close endpoint (demo).

**Tech Stack:** Backend: FastAPI, pytest (`TestClient`, offline fake client). Frontend: React + TanStack Query + Vitest + MSW. Reuses `usePriceStream` / `/ws/prices` unchanged.

Backend commands from `etoro/back/`; frontend from `etoro/front/`. Clean commits, **no** Co-Authored-By trailer. Repo branch `feat/yahoo-data-source` (controller syncs `main` after each task).

**Design source:** `docs/superpowers/specs/2026-06-04-portfolio-live-pnl-design.md`.

**P&L formula (used in Task 3 `pnl.ts`):** per position, with `price = liveLast ?? current_rate ?? null`:
`dir = is_buy ? 1 : -1` · `pnlUsd = units*(price - open_rate)*dir` · `pnlPct = amount ? pnlUsd/amount*100 : null`.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/data_cache/etoro_catalog.py` | + `get_by_instrument_ids(ids) -> {id: row}` |
| `back/routers/portfolio.py` | new: `Position`, `PortfolioResponse`, `GET /portfolio/positions`, `POST /portfolio/close/{id}` |
| `back/main.py` | include `portfolio.router` |
| `back/tests/test_portfolio.py` | new: normalization + enrichment + close path/guard |
| `front/src/types/portfolio.ts` | `Position`, `PortfolioResponse` |
| `front/src/api/portfolio.ts` | `fetchPortfolio`, `closePosition` |
| `front/src/lib/pnl.ts` | `positionPnl`, `aggregatePnl` (pure) |
| `front/src/hooks/usePortfolio.ts` | REST positions (refetch 30s) |
| `front/src/components/PortfolioSummary.tsx` | Σ invested / Σ P&L$ / total % |
| `front/src/components/PortfolioTable.tsx` | rows + live overlay + Close |
| `front/src/views/PortfolioView.tsx` | compose + close flow |
| `front/src/views/ScreenerView.tsx` | current `App` body, moved verbatim |
| `front/src/components/AppNav.tsx` | «Screener | Portfolio» toggle |
| `front/src/App.tsx` | thin shell: nav + active view |
| `front/src/__tests__/*` + `handlers.ts` | tests + MSW |

---

### Task 1: Catalog — `get_by_instrument_ids`

**Files:**
- Modify: `back/data_cache/etoro_catalog.py`
- Test: `back/tests/test_etoro_catalog.py`

- [ ] **Step 1: Write the failing test**

Append to `back/tests/test_etoro_catalog.py`:
```python
def test_get_by_instrument_ids(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1001, "asset_class": "Stocks",
         "display_name": "Apple", "exchange_name": "Nasdaq", "current_rate": 210.0},
        {"symbol": "MSFT", "instrument_id": 1002, "asset_class": "Stocks",
         "display_name": "Microsoft", "exchange_name": "Nasdaq", "current_rate": 400.0},
    ])
    m = cat.get_by_instrument_ids([1001, 99999])
    assert set(m.keys()) == {1001}                       # unknown id absent
    assert m[1001]["symbol"] == "AAPL" and m[1001]["current_rate"] == 210.0
    assert cat.get_by_instrument_ids([]) == {}
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_etoro_catalog.py -v -k get_by_instrument`
Expected: FAIL — `get_by_instrument_ids` not defined.

- [ ] **Step 3: Add the method to `back/data_cache/etoro_catalog.py`**

Add at the end of the `EtoroCatalog` class (after `exchanges`):
```python
    def get_by_instrument_ids(self, ids: Iterable[int]) -> dict[int, dict]:
        """Map instrument_id -> catalog row for the given ids. Unknown ids are omitted."""
        idlist = [int(i) for i in ids if i is not None]
        if not idlist:
            return {}
        placeholders = ",".join("?" * len(idlist))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE instrument_id IN ({placeholders})", idlist
            ).fetchall()
        return {r["instrument_id"]: dict(r) for r in rows}
```
(`Iterable` is already imported at the top of the file.)

- [ ] **Step 4: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_etoro_catalog.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add back/data_cache/etoro_catalog.py back/tests/test_etoro_catalog.py
git commit -m "feat(catalog): get_by_instrument_ids lookup"
```

---

### Task 2: Backend portfolio router

**Files:**
- Create: `back/routers/portfolio.py`
- Modify: `back/main.py`
- Test: `back/tests/test_portfolio.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_portfolio.py
import pytest
from fastapi.testclient import TestClient


class FakePortfolioClient:
    def __init__(self):
        self.closed = []

    def request(self, method, path, params=None, json=None):
        if method == "GET" and path.endswith("portfolio"):
            return {"clientPortfolio": {"positions": [
                {"positionID": 111, "instrumentID": 1137, "openRate": 215.81,
                 "isBuy": True, "units": 4.633061, "amount": 999.86, "leverage": 1},
                {"positionID": 222, "instrumentID": 99999, "openRate": 10.0,
                 "isBuy": False, "units": 5.0, "amount": 50.0, "leverage": 2},
            ]}}
        if method == "POST" and "market-close-orders" in path:
            self.closed.append((path, json))
            return {"ok": True}
        raise AssertionError(f"unexpected {method} {path}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import portfolio, screener
    from data_cache.etoro_catalog import EtoroCatalog
    db = tmp_path / "cat.db"
    EtoroCatalog(db).upsert([
        {"symbol": "ETH", "instrument_id": 1137, "asset_class": "Crypto",
         "display_name": "Ethereum", "exchange_name": "Digital Currency", "current_rate": 220.0},
    ])
    monkeypatch.setattr(screener, "CATALOG_DB", db)
    fake = FakePortfolioClient()
    monkeypatch.setattr(portfolio, "get_server_client", lambda: fake)
    from main import app
    tc = TestClient(app)
    tc.fake = fake
    return tc


def test_positions_normalizes_and_enriches(client):
    r = client.get("/portfolio/positions")
    assert r.status_code == 200
    body = r.json()
    assert body["account"] == "demo"
    pos = {p["position_id"]: p for p in body["positions"]}
    assert pos[111]["instrument_id"] == 1137
    assert pos[111]["symbol"] == "ETH" and pos[111]["name"] == "Ethereum"
    assert pos[111]["is_buy"] is True and pos[111]["open_rate"] == 215.81
    assert pos[111]["current_rate"] == 220.0
    assert pos[222]["symbol"] is None and pos[222]["is_buy"] is False   # unknown instrument


def test_close_calls_demo_path_with_body(client):
    r = client.post("/portfolio/close/111", json={"InstrumentID": 1137})
    assert r.status_code == 200 and r.json() == {"ok": True}
    path, payload = client.fake.closed[-1]
    assert "/demo/market-close-orders/positions/111" in path
    assert payload == {"InstrumentID": 1137}
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_portfolio.py -v`
Expected: FAIL — `routers.portfolio` does not exist / no routes.

- [ ] **Step 3: Create `back/routers/portfolio.py`**

```python
"""Portfolio view + live P&L (demo account, app keys) — see WS Spec 2.

Normalizes eToro open positions and enriches them from the instrument catalog
so the frontend can overlay live prices (via /ws/prices) and compute P&L.
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from etoro_api.server import get_server_client
from etoro_api.models import ClosePositionRequest
from routers.etoro.proxy import guard_real
from data_cache.etoro_catalog import EtoroCatalog

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class Position(BaseModel):
    position_id: int
    instrument_id: int
    symbol: Optional[str] = None
    name: Optional[str] = None
    is_buy: bool
    units: float
    open_rate: float
    amount: float
    leverage: float
    current_rate: Optional[float] = None


class PortfolioResponse(BaseModel):
    positions: list[Position]
    account: str


@router.get("/positions", response_model=PortfolioResponse)
def positions(account: str = Query("demo")):
    client = get_server_client()
    seg = "demo/" if account == "demo" else ""
    data = client.request("GET", f"/api/v1/trading/info/{seg}portfolio")
    raw = ((data or {}).get("clientPortfolio") or {}).get("positions") or []

    from routers import screener  # late import: lets tests monkeypatch screener.CATALOG_DB
    cat = EtoroCatalog(screener.CATALOG_DB)
    meta = cat.get_by_instrument_ids(
        [p.get("instrumentID") for p in raw if p.get("instrumentID") is not None])

    out: list[Position] = []
    for p in raw:
        iid = p.get("instrumentID")
        m = meta.get(iid, {})
        out.append(Position(
            position_id=p["positionID"], instrument_id=iid,
            symbol=m.get("symbol"), name=m.get("display_name"),
            is_buy=bool(p.get("isBuy")), units=p.get("units"),
            open_rate=p.get("openRate"), amount=p.get("amount"),
            leverage=p.get("leverage", 1) or 1, current_rate=m.get("current_rate"),
        ))
    return PortfolioResponse(positions=out, account=account)


@router.post("/close/{position_id}")
def close(position_id: int, body: ClosePositionRequest, account: str = Query("demo")):
    if account != "demo":
        guard_real()
    client = get_server_client()
    seg = "demo/" if account == "demo" else ""
    return client.request(
        "POST",
        f"/api/v1/trading/execution/{seg}market-close-orders/positions/{position_id}",
        json=body.model_dump(exclude_none=True))
```

- [ ] **Step 4: Wire into `back/main.py`**

Add `from routers import portfolio` next to `from routers import ws_prices`, and register it after `app.include_router(ws_prices.router)`:
```python
app.include_router(portfolio.router)
```

- [ ] **Step 5: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_portfolio.py -v` → PASS (2).
Then full backend suite `python -m pytest tests/ -q` → all pass. Then `python -c "import main; print('ok')"` → ok.

- [ ] **Step 6: Commit**

```bash
git add back/routers/portfolio.py back/main.py back/tests/test_portfolio.py
git commit -m "feat(portfolio): /portfolio/positions (normalized+enriched) + /portfolio/close"
```

---

### Task 3: Frontend types + API + `pnl.ts` + MSW

**Files:**
- Create: `front/src/types/portfolio.ts`, `front/src/api/portfolio.ts`, `front/src/lib/pnl.ts`, `front/src/__tests__/pnl.test.ts`, `front/src/__tests__/portfolioApi.test.ts`
- Modify: `front/src/__tests__/handlers.ts`

- [ ] **Step 1: Write the failing tests**

`front/src/__tests__/pnl.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { positionPnl, aggregatePnl } from "../lib/pnl";
import type { Position } from "../types/portfolio";

const buy: Position = { position_id: 1, instrument_id: 10, symbol: "ETH", name: "Ethereum",
  is_buy: true, units: 2, open_rate: 100, amount: 200, leverage: 1, current_rate: 110 };
const sell: Position = { position_id: 2, instrument_id: 11, symbol: "X", name: "X",
  is_buy: false, units: 3, open_rate: 50, amount: 150, leverage: 1, current_rate: 40 };

describe("positionPnl", () => {
  it("uses live last; buy profit = units*(last-open)", () => {
    expect(positionPnl(buy, 120)).toEqual({ price: 120, pnlUsd: 40, pnlPct: 20 });
  });
  it("falls back to current_rate when no live tick", () => {
    expect(positionPnl(buy, null)).toEqual({ price: 110, pnlUsd: 20, pnlPct: 10 });
  });
  it("sell profits when price drops", () => {
    expect(positionPnl(sell, 40)).toEqual({ price: 40, pnlUsd: 30, pnlPct: 20 });
  });
  it("null when no price at all", () => {
    expect(positionPnl({ ...buy, current_rate: null }, null))
      .toEqual({ price: null, pnlUsd: null, pnlPct: null });
  });
});

describe("aggregatePnl", () => {
  it("sums invested and pnl", () => {
    const agg = aggregatePnl([{ p: buy, price: 120 }, { p: sell, price: 40 }]);
    expect(agg.invested).toBe(350);
    expect(agg.pnlUsd).toBe(70);
    expect(agg.pnlPct).toBeCloseTo(20, 5);
  });
});
```

`front/src/__tests__/portfolioApi.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { fetchPortfolio, closePosition } from "../api/portfolio";

describe("fetchPortfolio", () => {
  it("returns positions + account", async () => {
    const r = await fetchPortfolio();
    expect(r.account).toBe("demo");
    expect(r.positions[0]).toHaveProperty("open_rate");
  });
});

describe("closePosition", () => {
  it("POSTs the body and resolves", async () => {
    const r = await closePosition(111, { InstrumentID: 1137 });
    expect(r).toBeTruthy();
  });
});
```

- [ ] **Step 2: Add MSW handlers**

In `front/src/__tests__/handlers.ts`, add to the `handlers` array (before the catch-all `/screener/:bad`):
```typescript
  http.get("/portfolio/positions", () =>
    HttpResponse.json({
      account: "demo",
      positions: [
        { position_id: 111, instrument_id: 1137, symbol: "ETH", name: "Ethereum",
          is_buy: true, units: 4.633061, open_rate: 215.81, amount: 999.86,
          leverage: 1, current_rate: 220 },
      ],
    })),
  http.post("/portfolio/close/:id", () => HttpResponse.json({ ok: true })),
```

- [ ] **Step 3: Run to verify it fails**

Run (from `front/`): `npm run test:run -- pnl portfolioApi`
Expected: FAIL — modules not found.

- [ ] **Step 4: Create `front/src/types/portfolio.ts`**

```typescript
export interface Position {
  position_id: number;
  instrument_id: number;
  symbol: string | null;
  name: string | null;
  is_buy: boolean;
  units: number;
  open_rate: number;
  amount: number;
  leverage: number;
  current_rate: number | null;
}

export interface PortfolioResponse {
  positions: Position[];
  account: string;
}
```

- [ ] **Step 5: Create `front/src/api/portfolio.ts`**

```typescript
import type { PortfolioResponse } from "../types/portfolio";

export async function fetchPortfolio(): Promise<PortfolioResponse> {
  const resp = await fetch("/portfolio/positions");
  if (!resp.ok) throw new Error(`Portfolio fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function closePosition(
  positionId: number, body: { InstrumentID: number; UnitsToDeduct?: number },
): Promise<unknown> {
  const resp = await fetch(`/portfolio/close/${positionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Close failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}
```

- [ ] **Step 6: Create `front/src/lib/pnl.ts`**

```typescript
import type { Position } from "../types/portfolio";

export interface PnlResult {
  price: number | null;
  pnlUsd: number | null;
  pnlPct: number | null;
}

export function positionPnl(p: Position, liveLast: number | null | undefined): PnlResult {
  const price = liveLast ?? p.current_rate ?? null;
  if (price === null) return { price: null, pnlUsd: null, pnlPct: null };
  const dir = p.is_buy ? 1 : -1;
  const pnlUsd = p.units * (price - p.open_rate) * dir;
  const pnlPct = p.amount ? (pnlUsd / p.amount) * 100 : null;
  return { price, pnlUsd, pnlPct };
}

export function aggregatePnl(rows: { p: Position; price: number | null }[]) {
  let invested = 0;
  let pnlUsd = 0;
  for (const { p, price } of rows) {
    invested += p.amount;
    if (price !== null) pnlUsd += p.units * (price - p.open_rate) * (p.is_buy ? 1 : -1);
  }
  const pnlPct = invested ? (pnlUsd / invested) * 100 : null;
  return { invested, pnlUsd, pnlPct };
}
```

- [ ] **Step 7: Run to verify it passes**

Run (from `front/`): `npm run test:run -- pnl portfolioApi` → PASS. Then full suite `npm run test:run` → all pass.

- [ ] **Step 8: Commit**

```bash
git add front/src/types/portfolio.ts front/src/api/portfolio.ts front/src/lib/pnl.ts front/src/__tests__/pnl.test.ts front/src/__tests__/portfolioApi.test.ts front/src/__tests__/handlers.ts
git commit -m "feat(front): portfolio types + api + pnl math + MSW"
```

---

### Task 4: `usePortfolio` + `PortfolioSummary` + `PortfolioTable`

**Files:**
- Create: `front/src/hooks/usePortfolio.ts`, `front/src/components/PortfolioSummary.tsx`, `front/src/components/PortfolioTable.tsx`, `front/src/__tests__/PortfolioTable.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/PortfolioTable.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PortfolioTable } from "../components/PortfolioTable";
import type { Position } from "../types/portfolio";
import type { LiveTick } from "../hooks/usePriceStream";

const rows: Position[] = [
  { position_id: 111, instrument_id: 1137, symbol: "ETH", name: "Ethereum",
    is_buy: true, units: 2, open_rate: 100, amount: 200, leverage: 1, current_rate: 110 },
];

describe("PortfolioTable", () => {
  it("renders a position with live P&L and fires onClose", async () => {
    const onClose = vi.fn();
    const ticks = new Map<number, LiveTick>([
      [1137, { bid: null, ask: null, last: 120, change_pct: null, ts: "T" }],
    ]);
    render(<PortfolioTable rows={rows} ticks={ticks} onClose={onClose} closingId={null} />);
    expect(screen.getByText("ETH")).toBeInTheDocument();
    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText("120.00")).toBeInTheDocument();   // live current
    expect(screen.getByText("+40.00")).toBeInTheDocument();   // pnl$ = 2*(120-100)
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledWith(rows[0]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- PortfolioTable`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the hook + components**

`front/src/hooks/usePortfolio.ts`:
```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchPortfolio } from "../api/portfolio";

export function usePortfolio() {
  return useQuery({ queryKey: ["portfolio"], queryFn: fetchPortfolio, refetchInterval: 30_000 });
}
```

`front/src/components/PortfolioSummary.tsx`:
```tsx
import { changeColorClass } from "../lib/formatters";

interface Props {
  invested: number;
  pnlUsd: number;
  pnlPct: number | null;
}

function signed(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

export function PortfolioSummary({ invested, pnlUsd, pnlPct }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-6 rounded-xl border border-border-default bg-bg-surface/40 px-6 py-4">
      <div>
        <div className="text-xs uppercase tracking-wide text-fg-muted">Invested</div>
        <div className="font-mono text-lg tabular-nums text-fg-default">${invested.toFixed(2)}</div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-fg-muted">Live P&L</div>
        <div className={["font-mono text-lg tabular-nums", changeColorClass(pnlUsd)].join(" ")}>
          {signed(pnlUsd)}
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-fg-muted">Return</div>
        <div className={["font-mono text-lg tabular-nums", changeColorClass(pnlPct ?? 0)].join(" ")}>
          {pnlPct === null ? "—" : `${signed(pnlPct)}%`}
        </div>
      </div>
    </div>
  );
}
```

`front/src/components/PortfolioTable.tsx`:
```tsx
import type { Position } from "../types/portfolio";
import type { LiveTick } from "../hooks/usePriceStream";
import { positionPnl } from "../lib/pnl";
import { changeColorClass } from "../lib/formatters";

interface Props {
  rows: Position[];
  ticks: Map<number, LiveTick>;
  onClose: (p: Position) => void;
  closingId: number | null;
}

function num(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}
function signed(v: number | null): string {
  return v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

export function PortfolioTable({ rows, ticks, onClose, closingId }: Props) {
  return (
    <div className="overflow-auto rounded-xl border border-border-default bg-bg-base">
      <table className="w-full text-sm">
        <thead className="text-left text-fg-muted border-b border-border-default">
          <tr>
            <th className="py-2.5 px-4">Market</th>
            <th className="py-2.5 px-4">Direction</th>
            <th className="py-2.5 px-4 text-right">Units</th>
            <th className="py-2.5 px-4 text-right">Open</th>
            <th className="py-2.5 px-4 text-right">Current</th>
            <th className="py-2.5 px-4 text-right">P&L $</th>
            <th className="py-2.5 px-4 text-right">P&L %</th>
            <th className="py-2.5 px-4"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const { price, pnlUsd, pnlPct } = positionPnl(p, ticks.get(p.instrument_id)?.last);
            return (
              <tr key={p.position_id} className="border-b border-border-default/50 hover:bg-bg-hover">
                <td className="py-2.5 px-4">
                  <span className="font-mono font-semibold text-fg-default">{p.symbol ?? `#${p.instrument_id}`}</span>
                  {p.name && <span className="ml-2 text-fg-muted">{p.name}</span>}
                </td>
                <td className="py-2.5 px-4">{p.is_buy ? "Buy" : "Sell"}</td>
                <td className="py-2.5 px-4 text-right font-mono tabular-nums">{p.units.toFixed(4)}</td>
                <td className="py-2.5 px-4 text-right font-mono tabular-nums">{p.open_rate.toFixed(2)}</td>
                <td className="py-2.5 px-4 text-right font-mono tabular-nums">{num(price)}</td>
                <td className={["py-2.5 px-4 text-right font-mono tabular-nums", changeColorClass(pnlUsd ?? 0)].join(" ")}>{signed(pnlUsd)}</td>
                <td className={["py-2.5 px-4 text-right font-mono tabular-nums", changeColorClass(pnlPct ?? 0)].join(" ")}>{pnlPct === null ? "—" : `${signed(pnlPct)}%`}</td>
                <td className="py-2.5 px-4 text-right">
                  <button
                    type="button"
                    onClick={() => onClose(p)}
                    disabled={closingId === p.position_id}
                    className="rounded-md border border-border-default bg-bg-surface px-3 py-1 text-xs font-medium text-fg-default hover:bg-bg-hover disabled:opacity-50"
                  >
                    {closingId === p.position_id ? "Closing…" : "Close"}
                  </button>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr><td colSpan={8} className="py-8 text-center text-fg-muted">No open positions.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```
NOTE: the test expects `getByText("+40.00")` for P&L$ and `getByText("120.00")` for current — `signed(40)` → "+40.00", `num(120)` → "120.00". `changeColorClass` already exists in `front/src/lib/formatters.ts` (used by ScreenerTable); verify its import path.

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- PortfolioTable` → PASS. Then full suite `npm run test:run` → all pass.

- [ ] **Step 5: Commit**

```bash
git add front/src/hooks/usePortfolio.ts front/src/components/PortfolioSummary.tsx front/src/components/PortfolioTable.tsx front/src/__tests__/PortfolioTable.test.tsx
git commit -m "feat(front): usePortfolio + PortfolioSummary + PortfolioTable"
```

---

### Task 5: `PortfolioView` (compose + close flow)

**Files:**
- Create: `front/src/views/PortfolioView.tsx`, `front/src/__tests__/PortfolioView.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/PortfolioView.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PortfolioView } from "../views/PortfolioView";

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><PortfolioView /></QueryClientProvider>);
}

describe("PortfolioView", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("loads positions and shows the summary + a row", async () => {
    renderView();
    await waitFor(() => expect(screen.getByText("ETH")).toBeInTheDocument());
    expect(screen.getByText(/Invested/i)).toBeInTheDocument();
  });

  it("close asks for confirmation then calls the API", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderView();
    await waitFor(() => expect(screen.getByText("ETH")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(window.confirm).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- PortfolioView`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `front/src/views/PortfolioView.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePortfolio } from "../hooks/usePortfolio";
import { usePriceStream } from "../hooks/usePriceStream";
import { closePosition } from "../api/portfolio";
import { positionPnl, aggregatePnl } from "../lib/pnl";
import { PortfolioSummary } from "../components/PortfolioSummary";
import { PortfolioTable } from "../components/PortfolioTable";
import type { Position } from "../types/portfolio";

export function PortfolioView() {
  const { data, isLoading, isError } = usePortfolio();
  const stream = usePriceStream();
  const qc = useQueryClient();
  const [closingId, setClosingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const positions = data?.positions ?? [];

  useEffect(() => {
    const ids = positions.map((p) => p.instrument_id);
    if (ids.length) stream.subscribe(ids);
  }, [data, stream]);

  const priced = positions.map((p) => ({
    p, price: positionPnl(p, stream.ticks.get(p.instrument_id)?.last).price,
  }));
  const agg = aggregatePnl(priced);

  async function onClose(p: Position) {
    if (!window.confirm(`Close ${p.symbol ?? p.instrument_id} (${p.is_buy ? "Buy" : "Sell"} ${p.units})?`)) return;
    setClosingId(p.position_id);
    setError(null);
    try {
      await closePosition(p.position_id, { InstrumentID: p.instrument_id });
      await qc.invalidateQueries({ queryKey: ["portfolio"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Close failed");
    } finally {
      setClosingId(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6 space-y-4">
      {isLoading && <p className="text-fg-muted">Loading portfolio…</p>}
      {isError && (
        <div className="text-accent-red">Could not load portfolio. Is the backend running on :8765?</div>
      )}
      {error && <div className="text-accent-red text-sm">{error}</div>}
      {data && (
        <>
          <PortfolioSummary invested={agg.invested} pnlUsd={agg.pnlUsd} pnlPct={agg.pnlPct} />
          <PortfolioTable rows={positions} ticks={stream.ticks} onClose={onClose} closingId={closingId} />
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- PortfolioView` → PASS (2). Then full suite `npm run test:run` → all pass.

- [ ] **Step 5: Commit**

```bash
git add front/src/views/PortfolioView.tsx front/src/__tests__/PortfolioView.test.tsx
git commit -m "feat(front): PortfolioView with live P&L + close flow"
```

---

### Task 6: AppNav + App shell (extract ScreenerView) + full verify

**Files:**
- Create: `front/src/views/ScreenerView.tsx`, `front/src/components/AppNav.tsx`, `front/src/__tests__/AppNav.test.tsx`
- Modify: `front/src/App.tsx`

- [ ] **Step 1: Extract the screener into `front/src/views/ScreenerView.tsx`**

Move the ENTIRE current contents of `front/src/App.tsx` into `front/src/views/ScreenerView.tsx` **verbatim**, with two changes:
1. Fix the relative import paths (they go up one more level now): change every `from "./` to `from "../` (e.g. `from "../hooks/useCategoryData"`, `from "../components/CategoryTabs"`, `from "../api/screener"`, `from "../types/screener"`).
2. Rename the export: change `export default function App() {` to `export function ScreenerView() {`.
Keep the helper functions (`freshness`, `TableSkeleton`, `SORTS`, `PAGE_SIZE`) and all markup exactly as-is.

- [ ] **Step 2: Write the AppNav test**

```tsx
// front/src/__tests__/AppNav.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppNav } from "../components/AppNav";

describe("AppNav", () => {
  it("renders both views and fires onChange", async () => {
    const onChange = vi.fn();
    render(<AppNav value="screener" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Screener" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Portfolio" }));
    expect(onChange).toHaveBeenCalledWith("portfolio");
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run (from `front/`): `npm run test:run -- AppNav`
Expected: FAIL — module not found.

- [ ] **Step 4: Write `front/src/components/AppNav.tsx`**

```tsx
export type AppView = "screener" | "portfolio";

const VIEWS: { id: AppView; label: string }[] = [
  { id: "screener", label: "Screener" },
  { id: "portfolio", label: "Portfolio" },
];

interface Props {
  value: AppView;
  onChange: (v: AppView) => void;
}

export function AppNav({ value, onChange }: Props) {
  return (
    <nav className="mx-auto flex w-full max-w-[1400px] items-center gap-1 px-6 py-2">
      {VIEWS.map(({ id, label }) => {
        const active = id === value;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(id)}
            className={[
              "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              "outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70",
              active ? "bg-bg-hover text-fg-default" : "text-fg-muted hover:text-fg-default hover:bg-bg-hover/60",
            ].join(" ")}
          >
            {label}
          </button>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 5: Rewrite `front/src/App.tsx` as the thin shell**

```tsx
import { useState } from "react";
import { AppNav, type AppView } from "./components/AppNav";
import { ScreenerView } from "./views/ScreenerView";
import { PortfolioView } from "./views/PortfolioView";

export default function App() {
  const [view, setView] = useState<AppView>("screener");
  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg-default">
      <div className="border-b border-border-default bg-bg-base/90">
        <AppNav value={view} onChange={setView} />
      </div>
      {view === "screener" ? <ScreenerView /> : <PortfolioView />}
    </div>
  );
}
```

- [ ] **Step 6: Update the existing App test for the nav**

The existing `front/src/__tests__/App.test.tsx` mounts `<App/>` and asserts the Crypto tab + a Bitcoin row — these still render because the default view is "screener". Add one assertion that the nav exists, and a switch test. Append inside its `describe("App", ...)`:
```tsx
  it("switches to the Portfolio view", async () => {
    renderApp();
    await userEvent.click(screen.getByRole("button", { name: "Portfolio" }));
    await waitFor(() => expect(screen.getByText(/Invested/i)).toBeInTheDocument());
  });
```
(If `userEvent`/`waitFor` aren't imported in that file, add them to the existing imports from `@testing-library/user-event` and `@testing-library/react`.)

- [ ] **Step 7: Run the full suite + build**

Run (from `front/`): `npm run test:run` → all PASS (ScreenerView renders the same screener content the old App test expects; the new switch test reaches PortfolioView via the MSW `/portfolio/positions` handler). Then `npm run build` (`tsc -b && vite build`) → clean, no type errors. If `ScreenerView` import paths cause a type error, fix the `./`→`../` paths until clean.

- [ ] **Step 8: Live verify (backend on 8765 already running — user-managed)**

```bash
curl -s "http://127.0.0.1:8765/portfolio/positions" | python -c "import sys,json;d=json.load(sys.stdin);print('account',d['account'],'positions',len(d['positions']));[print(' ',p['symbol'] or p['instrument_id'],'open',p['open_rate'],'units',p['units'],p['is_buy'] and 'BUY' or 'SELL') for p in d['positions'][:5]]"
```
Expected: the demo account's open positions with `open_rate`/`units`/`is_buy`. Frontend (`npm run dev`): the «Portfolio» tab shows the positions; P&L $/% update live as ticks arrive; clicking Close (confirm) closes the position and the list refreshes. (Skip the GUI step if no display; the curl confirms the backend half.)

- [ ] **Step 9: Commit**

```bash
git add front/src/views/ScreenerView.tsx front/src/components/AppNav.tsx front/src/App.tsx front/src/__tests__/AppNav.test.tsx front/src/__tests__/App.test.tsx
git commit -m "feat(front): Screener|Portfolio nav shell + ScreenerView extraction"
```

---

## Self-Review notes

- **Spec coverage:** catalog `get_by_instrument_ids` (Task 1) ↔ spec "EtoroCatalog.get_by_instrument_ids"; `/portfolio/positions` + `/close` (Task 2) ↔ "routers/portfolio.py"; types/api/pnl/MSW (Task 3) ↔ "types/api" + "lib/pnl" + "Live P&L formula"; `usePortfolio`/`PortfolioSummary`/`PortfolioTable` (Task 4) ↔ "hooks/components"; `PortfolioView` close flow (Task 5) ↔ "views/PortfolioView" + "Close"; AppNav + App shell + ScreenerView (Task 6) ↔ "AppNav"/"App.tsx" + "ScreenerView extraction" + live verify. P&L reuses `usePriceStream`/`/ws/prices` unchanged. ✓
- **Type/name consistency:** `Position` fields (`position_id, instrument_id, symbol, name, is_buy, units, open_rate, amount, leverage, current_rate`) identical in backend Pydantic (Task 2), TS type (Task 3), `pnl.ts` (Task 3), `PortfolioTable`/`PortfolioView` (Tasks 4–5), MSW (Task 3) and backend test (Task 2). `positionPnl`/`aggregatePnl` signatures match call sites. `closePosition(id, {InstrumentID})` body matches the backend `ClosePositionRequest` + the close test. `AppView` type shared by AppNav + App. ✓
- **Placeholders:** none. **Deps:** none new. **Reuse:** `usePriceStream`/`/ws/prices`/`changeColorClass` reused; relay untouched. **Account:** demo (server keys); real guarded. **Sticky nav:** AppNav is a plain top bar (non-sticky) so ScreenerView's existing `sticky top-0`/`top-[65px]` offsets stay valid — no sticky-chain change.
```
