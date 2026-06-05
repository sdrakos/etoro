# Interactive instrument chart (KLineCharts) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Click a stock (Screener/Portfolio) → open a new browser tab with a professional, interactive KLineCharts candlestick chart with TA indicators + live last-candle updates.

**Architecture:** A new server-client backend endpoint serves normalized eToro OHLCV candles. The React app gains `react-router-dom` with a standalone `/chart/:instrumentId` route (opened via `window.open`); `ChartView` renders KLineCharts (candles + volume + toggleable indicators), refetches on timeframe change, and updates the last candle live from the existing `/ws/prices` relay.

**Tech Stack:** Backend: FastAPI, pytest. Frontend: React + react-router-dom + klinecharts + TanStack Query + Vitest + MSW. Reuses `usePriceStream` / `/ws/prices`.

Backend from `etoro/back/`; frontend from `etoro/front/`. Clean commits, **no** Co-Authored-By trailer. Branch `feat/yahoo-data-source` (controller syncs `main` after each task).

**Design source:** `docs/superpowers/specs/2026-06-05-instrument-chart-design.md`.

**Naming (avoid collision):** backend API prefix `/charts` (plural); frontend browser route `/chart/:id` (singular). Vite proxies `/charts` → 8765; `/chart` stays a frontend route.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/routers/chart.py` | new: `GET /charts/{instrument_id}` (normalized eToro candles + catalog enrich) |
| `back/main.py` | include `chart.router` |
| `back/tests/test_chart.py` | new: normalization (flatten/ascending/epoch-ms/drop-incomplete) + enrich |
| `front/package.json` | + `klinecharts`, `react-router-dom` |
| `front/vite.config.ts` | + `/charts` proxy |
| `front/src/types/chart.ts` | `Candle`, `ChartResponse` |
| `front/src/lib/intervals.ts` | `TIMEFRAMES`, `toEtoroInterval` (pure) |
| `front/src/lib/openChart.ts` | `openChart(id)` → window.open |
| `front/src/lib/chartLive.ts` | `liveCandle(last, price)` (pure) |
| `front/src/api/chart.ts` | `fetchChart(id, interval)` |
| `front/src/hooks/useChartData.ts` | TanStack Query |
| `front/src/components/Chart.tsx` | KLineCharts wrapper (init/apply/indicators/updateLast) |
| `front/src/components/ChartToolbar.tsx` | timeframe + indicator toggles |
| `front/src/views/ChartView.tsx` | standalone chart page |
| `front/src/AppRoutes.tsx` | routes `/` + `/chart/:instrumentId` |
| `front/src/main.tsx` | wrap in `BrowserRouter` + `AppRoutes` |
| `front/src/components/{ScreenerTable,PortfolioTable}.tsx` | ticker becomes clickable → `openChart` |

---

### Task 1: Backend candles endpoint

**Files:**
- Create: `back/routers/chart.py`
- Modify: `back/main.py`
- Test: `back/tests/test_chart.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_chart.py
import pytest
from fastapi.testclient import TestClient


class FakeCandleClient:
    def request(self, method, path, params=None, json=None):
        assert "history/candles/desc/OneDay/300" in path
        return {"interval": "OneDay", "candles": [{"instrumentId": 1001, "candles": [
            {"fromDate": "2026-06-05T00:00:00Z", "open": 311.11, "high": 311.68, "low": 310.15, "close": 310.57, "volume": 10115.0},
            {"fromDate": "2026-06-04T00:00:00Z", "open": 311.29, "high": 314.7, "low": 309.66, "close": 311.11, "volume": 36125964.0},
            {"fromDate": "bad-date", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": None},
            {"fromDate": "2026-06-03T00:00:00Z", "open": None, "high": 1.0, "low": 1.0, "close": 1.0, "volume": None},
        ]}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from routers import chart, screener
    from data_cache.etoro_catalog import EtoroCatalog
    db = tmp_path / "cat.db"
    EtoroCatalog(db).upsert([{"symbol": "AAPL", "instrument_id": 1001,
                              "asset_class": "Stocks", "display_name": "Apple"}])
    monkeypatch.setattr(screener, "CATALOG_DB", db)
    monkeypatch.setattr(chart, "get_server_client", lambda: FakeCandleClient())
    from main import app
    return TestClient(app)


def test_chart_normalizes_ascending_epoch_ms_and_enriches(client):
    r = client.get("/charts/1001?interval=OneDay&count=300")
    assert r.status_code == 200
    b = r.json()
    assert b["instrument_id"] == 1001 and b["symbol"] == "AAPL" and b["name"] == "Apple"
    assert b["interval"] == "OneDay"
    # bad-date and missing-open dropped → 2 candles
    assert len(b["candles"]) == 2
    times = [c["time"] for c in b["candles"]]
    assert times == sorted(times)                              # ascending
    assert all(isinstance(t, int) and t > 1_000_000_000_000 for t in times)  # epoch ms
    # ascending: 06-04 (open 311.29) then 06-05 (open 311.11)
    assert b["candles"][0]["open"] == 311.29 and b["candles"][1]["open"] == 311.11
    assert b["candles"][1]["volume"] == 10115.0
```

- [ ] **Step 2: Run to verify it fails**

Run (from `back/`): `python -m pytest tests/test_chart.py -v`
Expected: FAIL — `routers.chart` does not exist.

- [ ] **Step 3: Create `back/routers/chart.py`**

```python
"""eToro candlestick data for the chart view (server client, demo)."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from etoro_api.server import get_server_client
from data_cache.etoro_catalog import EtoroCatalog

router = APIRouter(prefix="/charts", tags=["charts"])


class Candle(BaseModel):
    time: int          # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class ChartResponse(BaseModel):
    instrument_id: int
    symbol: Optional[str] = None
    name: Optional[str] = None
    interval: str
    candles: list[Candle]


def _epoch_ms(iso) -> Optional[int]:
    if not isinstance(iso, str):
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


@router.get("/{instrument_id}", response_model=ChartResponse)
def chart(instrument_id: int, interval: str = Query("OneDay"),
          count: int = Query(300), account: str = Query("demo")):
    count = max(1, min(count, 1000))
    client = get_server_client()
    raw = client.request(
        "GET",
        f"/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/{interval}/{count}")
    groups = (raw or {}).get("candles") or []
    inner = (groups[0].get("candles") if groups else []) or []

    out: list[Candle] = []
    for c in inner:
        t = _epoch_ms(c.get("fromDate"))
        o, h, l, cl = c.get("open"), c.get("high"), c.get("low"), c.get("close")
        if t is None or None in (o, h, l, cl):
            continue
        out.append(Candle(time=t, open=o, high=h, low=l, close=cl, volume=c.get("volume")))
    out.sort(key=lambda x: x.time)

    from routers import screener  # late import: lets tests monkeypatch screener.CATALOG_DB
    meta = (EtoroCatalog(screener.CATALOG_DB)
            .get_by_instrument_ids([instrument_id]).get(instrument_id, {}))
    return ChartResponse(instrument_id=instrument_id, symbol=meta.get("symbol"),
                         name=meta.get("display_name"), interval=interval, candles=out)
```

- [ ] **Step 4: Wire into `back/main.py`**

Add `from routers import chart` next to `from routers import ws_prices`, and `app.include_router(chart.router)` after `app.include_router(portfolio.router)`.

- [ ] **Step 5: Run to verify it passes**

Run (from `back/`): `python -m pytest tests/test_chart.py -v` → PASS. Then full backend suite `python -m pytest tests/ -q` → all pass. Then `python -c "import main; print('ok')"` → ok.

- [ ] **Step 6: Commit**

```bash
git add back/routers/chart.py back/main.py back/tests/test_chart.py
git commit -m "feat(charts): GET /charts/{id} normalized eToro candles + catalog enrich"
```

---

### Task 2: Frontend deps + types + api + pure libs

**Files:**
- Modify: `front/package.json` (via npm install), `front/vite.config.ts`, `front/src/__tests__/handlers.ts`
- Create: `front/src/types/chart.ts`, `front/src/lib/intervals.ts`, `front/src/lib/openChart.ts`, `front/src/lib/chartLive.ts`, `front/src/api/chart.ts`, `front/src/hooks/useChartData.ts`, `front/src/__tests__/chartLib.test.ts`

- [ ] **Step 1: Install dependencies**

Run (from `front/`): `npm install klinecharts@^9.8.0 react-router-dom@^6.26.0`
Expected: both added to `dependencies` in `package.json`; `npm run test:run` still green afterward.

- [ ] **Step 2: Add the `/charts` proxy in `front/vite.config.ts`**

Change the `proxy` block to add the charts line (keep the others):
```typescript
    proxy: {
      "/screener": "http://localhost:8765",
      "/portfolio": "http://localhost:8765",
      "/charts": "http://localhost:8765",
      "/ws": { target: "ws://localhost:8765", ws: true },
    },
```

- [ ] **Step 3: Write the failing test**

```typescript
// front/src/__tests__/chartLib.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toEtoroInterval, TIMEFRAMES } from "../lib/intervals";
import { liveCandle } from "../lib/chartLive";
import { openChart } from "../lib/openChart";
import { fetchChart } from "../api/chart";
import type { Candle } from "../types/chart";

describe("intervals", () => {
  it("maps UI timeframe → eToro interval, defaults to OneDay", () => {
    expect(toEtoroInterval("1h")).toBe("OneHour");
    expect(toEtoroInterval("1w")).toBe("OneWeek");
    expect(toEtoroInterval("nonsense")).toBe("OneDay");
    expect(TIMEFRAMES.find((t) => t.id === "1d")?.etoro).toBe("OneDay");
  });
});

describe("liveCandle", () => {
  it("merges a live price into the last candle (close + extend high/low)", () => {
    const last: Candle = { time: 1, open: 100, high: 105, low: 95, close: 102, volume: 10 };
    expect(liveCandle(last, 110)).toEqual({ time: 1, open: 100, high: 110, low: 95, close: 110, volume: 10 });
    expect(liveCandle(last, 90)).toEqual({ time: 1, open: 100, high: 105, low: 90, close: 90, volume: 10 });
  });
});

describe("openChart", () => {
  beforeEach(() => { vi.restoreAllMocks(); });
  it("opens /chart/{id} in a new tab", () => {
    const spy = vi.spyOn(window, "open").mockReturnValue(null);
    openChart(100000);
    expect(spy).toHaveBeenCalledWith("/chart/100000", "_blank", "noopener");
  });
});

describe("fetchChart", () => {
  it("returns a chart response with candles", async () => {
    const r = await fetchChart(1001, "OneDay");
    expect(r.symbol).toBe("AAPL");
    expect(r.candles.length).toBeGreaterThan(0);
    expect(r.candles[0]).toHaveProperty("time");
  });
});
```

- [ ] **Step 4: Add the MSW handler**

In `front/src/__tests__/handlers.ts`, add to the `handlers` array (before the catch-all `/screener/:bad`):
```typescript
  http.get("/charts/:id", ({ params }) =>
    HttpResponse.json({
      instrument_id: Number(params.id), symbol: "AAPL", name: "Apple", interval: "OneDay",
      candles: [
        { time: 1717459200000, open: 311.29, high: 314.7, low: 309.66, close: 311.11, volume: 36125964 },
        { time: 1717545600000, open: 311.11, high: 311.68, low: 310.15, close: 310.57, volume: 10115 },
      ],
    })),
```

- [ ] **Step 5: Run to verify it fails**

Run (from `front/`): `npm run test:run -- chartLib`
Expected: FAIL — modules not found.

- [ ] **Step 6: Create the files**

`front/src/types/chart.ts`:
```typescript
export interface Candle {
  time: number;   // epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface ChartResponse {
  instrument_id: number;
  symbol: string | null;
  name: string | null;
  interval: string;
  candles: Candle[];
}
```

`front/src/lib/intervals.ts`:
```typescript
export interface Timeframe {
  id: string;
  label: string;
  etoro: string;
}

export const TIMEFRAMES: Timeframe[] = [
  { id: "5m", label: "5m", etoro: "FiveMinutes" },
  { id: "15m", label: "15m", etoro: "FifteenMinutes" },
  { id: "1h", label: "1H", etoro: "OneHour" },
  { id: "4h", label: "4H", etoro: "FourHours" },
  { id: "1d", label: "1D", etoro: "OneDay" },
  { id: "1w", label: "1W", etoro: "OneWeek" },
];

export function toEtoroInterval(id: string): string {
  return TIMEFRAMES.find((t) => t.id === id)?.etoro ?? "OneDay";
}
```

`front/src/lib/openChart.ts`:
```typescript
export function openChart(instrumentId: number): void {
  window.open(`/chart/${instrumentId}`, "_blank", "noopener");
}
```

`front/src/lib/chartLive.ts`:
```typescript
import type { Candle } from "../types/chart";

/** Merge a live price into the last candle: set close, extend high/low. */
export function liveCandle(last: Candle, price: number): Candle {
  return {
    ...last,
    close: price,
    high: Math.max(last.high, price),
    low: Math.min(last.low, price),
  };
}
```

`front/src/api/chart.ts`:
```typescript
import type { ChartResponse } from "../types/chart";

export async function fetchChart(instrumentId: number, interval: string): Promise<ChartResponse> {
  const qs = new URLSearchParams({ interval, count: "300" });
  const resp = await fetch(`/charts/${instrumentId}?${qs.toString()}`);
  if (!resp.ok) throw new Error(`Chart fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}
```

`front/src/hooks/useChartData.ts`:
```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchChart } from "../api/chart";

export function useChartData(instrumentId: number, interval: string) {
  return useQuery({
    queryKey: ["chart", instrumentId, interval],
    queryFn: () => fetchChart(instrumentId, interval),
    enabled: Number.isFinite(instrumentId) && instrumentId > 0,
  });
}
```

- [ ] **Step 7: Run to verify it passes**

Run (from `front/`): `npm run test:run -- chartLib` → PASS (4 describes). Then full suite `npm run test:run` → all pass.

- [ ] **Step 8: Commit**

```bash
git add front/package.json front/package-lock.json front/vite.config.ts front/src/types/chart.ts front/src/lib/intervals.ts front/src/lib/openChart.ts front/src/lib/chartLive.ts front/src/api/chart.ts front/src/hooks/useChartData.ts front/src/__tests__/handlers.ts front/src/__tests__/chartLib.test.ts
git commit -m "feat(front): chart deps + types + api + intervals/openChart/liveCandle libs"
```

---

### Task 3: `Chart` (KLineCharts wrapper) + `ChartToolbar`

**Files:**
- Create: `front/src/components/Chart.tsx`, `front/src/components/ChartToolbar.tsx`, `front/src/__tests__/Chart.test.tsx`, `front/src/__tests__/ChartToolbar.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// front/src/__tests__/Chart.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { init } from "klinecharts";
import { Chart } from "../components/Chart";
import type { Candle } from "../types/chart";

vi.mock("klinecharts", () => {
  const chart = {
    applyNewData: vi.fn(),
    createIndicator: vi.fn(() => "pane_1"),
    removeIndicator: vi.fn(),
    updateData: vi.fn(),
  };
  return { init: vi.fn(() => chart), dispose: vi.fn() };
});

const candles: Candle[] = [
  { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
];

describe("Chart", () => {
  it("inits klinecharts, applies data, and creates the active indicators", () => {
    render(<Chart candles={candles} indicators={["MA", "VOL"]} />);
    expect(init).toHaveBeenCalled();
    const chart = (init as unknown as { mock: { results: { value: any }[] } }).mock.results[0].value;
    expect(chart.applyNewData).toHaveBeenCalledWith([
      { timestamp: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    ]);
    const names = chart.createIndicator.mock.calls.map((c: any[]) => c[0]);
    expect(names).toContain("MA");
    expect(names).toContain("VOL");
  });
});
```

```tsx
// front/src/__tests__/ChartToolbar.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChartToolbar } from "../components/ChartToolbar";

describe("ChartToolbar", () => {
  it("renders timeframes + indicators and fires callbacks", async () => {
    const onTimeframe = vi.fn();
    const onToggle = vi.fn();
    render(<ChartToolbar timeframe="1d" onTimeframe={onTimeframe}
                         active={new Set(["MA", "VOL"])} onToggle={onToggle} />);
    expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "1H" }));
    expect(onTimeframe).toHaveBeenCalledWith("1h");
    await userEvent.click(screen.getByRole("button", { name: "RSI" }));
    expect(onToggle).toHaveBeenCalledWith("RSI");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run (from `front/`): `npm run test:run -- Chart ChartToolbar`
Expected: FAIL — modules not found.

- [ ] **Step 3: Write the components**

`front/src/components/Chart.tsx`:
```tsx
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { init, dispose } from "klinecharts";
import type { Candle } from "../types/chart";

export interface ChartHandle {
  updateLast: (c: Candle) => void;
}

interface Props {
  candles: Candle[];
  indicators: string[];
}

// Indicators drawn ON the candle pane (overlays) vs. their own sub-pane.
const MAIN_OVERLAYS = ["MA", "EMA", "BOLL"];

function toKline(c: Candle) {
  return { timestamp: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
           volume: c.volume ?? undefined };
}

export const Chart = forwardRef<ChartHandle, Props>(function Chart({ candles, indicators }, ref) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof init> | null>(null);
  const panes = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    chartRef.current = init(elRef.current!);
    return () => {
      if (elRef.current) dispose(elRef.current);
      chartRef.current = null;
      panes.current.clear();
    };
  }, []);

  useEffect(() => {
    chartRef.current?.applyNewData(candles.map(toKline));
  }, [candles]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const active = new Set(indicators);
    for (const [name, paneId] of [...panes.current]) {
      if (!active.has(name)) {
        chart.removeIndicator(paneId, name);
        panes.current.delete(name);
      }
    }
    for (const name of active) {
      if (panes.current.has(name)) continue;
      if (MAIN_OVERLAYS.includes(name)) {
        chart.createIndicator(name, false, { id: "candle_pane" });
        panes.current.set(name, "candle_pane");
      } else {
        const paneId = chart.createIndicator(name);
        if (paneId) panes.current.set(name, paneId);
      }
    }
  }, [indicators]);

  useImperativeHandle(ref, () => ({
    updateLast: (c) => chartRef.current?.updateData(toKline(c)),
  }), []);

  return <div ref={elRef} className="h-full w-full" />;
});
```

`front/src/components/ChartToolbar.tsx`:
```tsx
import { TIMEFRAMES } from "../lib/intervals";

const INDICATORS = ["MA", "EMA", "BOLL", "VOL", "MACD", "RSI", "KDJ"];

interface Props {
  timeframe: string;
  onTimeframe: (id: string) => void;
  active: Set<string>;
  onToggle: (name: string) => void;
}

const btn =
  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors outline-none " +
  "focus-visible:ring-2 focus-visible:ring-accent-blue/70";

export function ChartToolbar({ timeframe, onTimeframe, active, onToggle }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border-default px-4 py-2">
      <div className="flex gap-1">
        {TIMEFRAMES.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-pressed={t.id === timeframe}
            onClick={() => onTimeframe(t.id)}
            className={[btn, t.id === timeframe ? "bg-accent-blue text-white"
              : "text-fg-muted hover:text-fg-default hover:bg-bg-hover"].join(" ")}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="ml-auto flex flex-wrap gap-1">
        {INDICATORS.map((n) => (
          <button
            key={n}
            type="button"
            aria-pressed={active.has(n)}
            onClick={() => onToggle(n)}
            className={[btn, active.has(n) ? "bg-bg-hover text-fg-default"
              : "text-fg-muted hover:text-fg-default hover:bg-bg-hover/60"].join(" ")}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify they pass**

Run (from `front/`): `npm run test:run -- Chart ChartToolbar` → PASS. Then full suite `npm run test:run` → all pass.

- [ ] **Step 5: Commit**

```bash
git add front/src/components/Chart.tsx front/src/components/ChartToolbar.tsx front/src/__tests__/Chart.test.tsx front/src/__tests__/ChartToolbar.test.tsx
git commit -m "feat(front): KLineCharts wrapper + indicator/timeframe toolbar"
```

---

### Task 4: `ChartView` + routing

**Files:**
- Create: `front/src/views/ChartView.tsx`, `front/src/AppRoutes.tsx`, `front/src/__tests__/ChartView.test.tsx`
- Modify: `front/src/main.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/ChartView.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChartView } from "../views/ChartView";

vi.mock("klinecharts", () => {
  const chart = { applyNewData: vi.fn(), createIndicator: vi.fn(() => "p"), removeIndicator: vi.fn(), updateData: vi.fn() };
  return { init: vi.fn(() => chart), dispose: vi.fn() };
});

function renderChart() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/chart/1001"]}>
        <Routes>
          <Route path="/chart/:instrumentId" element={<ChartView />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ChartView", () => {
  it("loads candles and shows the symbol header + toolbar", async () => {
    renderChart();
    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "1D" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- ChartView`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `front/src/views/ChartView.tsx`**

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useChartData } from "../hooks/useChartData";
import { usePriceStream } from "../hooks/usePriceStream";
import { Chart, type ChartHandle } from "../components/Chart";
import { ChartToolbar } from "../components/ChartToolbar";
import { toEtoroInterval } from "../lib/intervals";
import { liveCandle } from "../lib/chartLive";

export function ChartView() {
  const { instrumentId } = useParams();
  const id = Number(instrumentId);
  const [tf, setTf] = useState("1d");
  const [active, setActive] = useState<Set<string>>(new Set(["MA", "VOL"]));
  const { data, isLoading, isError } = useChartData(id, toEtoroInterval(tf));
  const stream = usePriceStream();
  const chartRef = useRef<ChartHandle>(null);

  useEffect(() => {
    if (Number.isFinite(id) && id > 0) stream.subscribe([id]);
  }, [id, stream]);

  const candles = useMemo(() => data?.candles ?? [], [data]);

  useEffect(() => {
    const last = candles[candles.length - 1];
    const price = stream.ticks.get(id)?.last;
    if (last && price != null) chartRef.current?.updateLast(liveCandle(last, price));
  }, [stream.ticks, id, candles]);

  const toggle = (name: string) =>
    setActive((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const livePrice = stream.ticks.get(id)?.last;

  return (
    <div className="flex h-screen flex-col bg-bg-base text-fg-default">
      <header className="flex items-baseline gap-3 border-b border-border-default px-4 py-3">
        <span className="font-mono text-lg font-semibold">{data?.symbol ?? `#${id}`}</span>
        {data?.name && <span className="text-sm text-fg-muted">{data.name}</span>}
        {livePrice != null && (
          <span className="ml-auto font-mono tabular-nums text-accent-green">{livePrice.toFixed(2)}</span>
        )}
      </header>
      <ChartToolbar timeframe={tf} onTimeframe={setTf} active={active} onToggle={toggle} />
      <main className="relative flex-1">
        {isLoading && <p className="p-4 text-fg-muted">Loading chart…</p>}
        {isError && (
          <p className="p-4 text-accent-red">Could not load chart. Is the backend running on :8765?</p>
        )}
        {data && candles.length === 0 && (
          <p className="p-4 text-fg-muted">No chart data for this instrument.</p>
        )}
        {data && candles.length > 0 && (
          <Chart ref={chartRef} candles={candles} indicators={[...active]} />
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Create `front/src/AppRoutes.tsx`**

```tsx
import { Routes, Route } from "react-router-dom";
import App from "./App";
import { ChartView } from "./views/ChartView";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/chart/:instrumentId" element={<ChartView />} />
    </Routes>
  );
}
```

- [ ] **Step 5: Wrap `front/src/main.tsx` in the router**

Replace its render block. Add imports `import { BrowserRouter } from "react-router-dom";` and `import { AppRoutes } from "./AppRoutes";` (remove the `import App from "./App";` line — App is now reached via AppRoutes), and change the JSX:
```tsx
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 6: Run to verify it passes**

Run (from `front/`): `npm run test:run -- ChartView` → PASS. Then full suite `npm run test:run` → all pass. Then `npm run build` (`tsc -b && vite build`) → clean.

- [ ] **Step 7: Commit**

```bash
git add front/src/views/ChartView.tsx front/src/AppRoutes.tsx front/src/main.tsx front/src/__tests__/ChartView.test.tsx
git commit -m "feat(front): ChartView + react-router (/chart/:id) + live last-candle"
```

---

### Task 5: Make tickers clickable + full verify

**Files:**
- Modify: `front/src/components/ScreenerTable.tsx`, `front/src/components/PortfolioTable.tsx`
- Test: `front/src/__tests__/chartWiring.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/chartWiring.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScreenerTable } from "../components/ScreenerTable";
import { PortfolioTable } from "../components/PortfolioTable";
import { openChart } from "../lib/openChart";
import type { CategoryRow } from "../types/screener";
import type { Position } from "../types/portfolio";

vi.mock("../lib/openChart", () => ({ openChart: vi.fn() }));

const srow: CategoryRow = { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
  exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010, change_pct: 8.3,
  sentiment_buy_pct: 90, is_open: true, volume: null, market_cap: null, pe_ratio: null };
const prow: Position = { position_id: 111, instrument_id: 1137, symbol: "NVDA", name: "NVIDIA",
  is_buy: true, units: 2, open_rate: 100, amount: 200, leverage: 1, current_rate: 110 };

describe("chart wiring", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("ScreenerTable ticker opens the chart", async () => {
    render(<ScreenerTable rows={[srow]} />);
    await userEvent.click(screen.getByRole("button", { name: "BTC" }));
    expect(openChart).toHaveBeenCalledWith(100000);
  });

  it("PortfolioTable symbol opens the chart", async () => {
    render(<PortfolioTable rows={[prow]} ticks={new Map()} onClose={() => {}} closingId={null} />);
    await userEvent.click(screen.getByRole("button", { name: "NVDA" }));
    expect(openChart).toHaveBeenCalledWith(1137);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- chartWiring`
Expected: FAIL — tickers are plain `<span>`, not buttons calling `openChart`.

- [ ] **Step 3: Make the ScreenerTable ticker clickable**

In `front/src/components/ScreenerTable.tsx`, add the import at the top:
```tsx
import { openChart } from "../lib/openChart";
```
Find the Market-cell ticker (currently a `<span className="font-mono font-semibold tracking-tight text-fg-default">{r.ticker}</span>`) and replace that span with a button:
```tsx
                    <button
                      type="button"
                      onClick={() => r.instrument_id != null && openChart(r.instrument_id)}
                      className="font-mono font-semibold tracking-tight text-fg-default hover:text-accent-blue hover:underline outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70 rounded"
                    >
                      {r.ticker}
                    </button>
```

- [ ] **Step 4: Make the PortfolioTable symbol clickable**

In `front/src/components/PortfolioTable.tsx`, add `import { openChart } from "../lib/openChart";` at the top. Find the Market cell's symbol (currently `<span className="font-mono font-semibold text-fg-default">{p.symbol ?? \`#${p.instrument_id}\`}</span>`) and replace that span with:
```tsx
                  <button
                    type="button"
                    onClick={() => openChart(p.instrument_id)}
                    className="font-mono font-semibold text-fg-default hover:text-accent-blue hover:underline outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70 rounded"
                  >
                    {p.symbol ?? `#${p.instrument_id}`}
                  </button>
```

- [ ] **Step 5: Run to verify it passes**

Run (from `front/`): `npm run test:run -- chartWiring` → PASS (2). Then the FULL suite `npm run test:run` → all pass. NOTE: the existing `ScreenerTable.test.tsx` asserts `getByText("BTC")` and the existing `PortfolioTable.test.tsx` asserts `getByText("ETH")` — these still pass because the ticker text is now inside a `<button>` (text content unchanged). If either now reports "multiple elements", scope it; otherwise leave them. Then `npm run build` → clean.

- [ ] **Step 6: Live verify (backend on 8765 — user-managed)**

```bash
curl -s "http://127.0.0.1:8765/charts/1001?interval=OneDay&count=5" | python -c "import sys,json;d=json.load(sys.stdin);print(d['symbol'],d['name'],'candles',len(d['candles']));print('  first',d['candles'][0]);print('  ascending',[c['time'] for c in d['candles']]==sorted(c['time'] for c in d['candles']))"
```
Expected: `AAPL Apple candles 5`, ascending times, OHLCV present. Frontend (`npm run dev`): click a ticker in the Screener → a new tab opens at `/chart/{id}` with a candlestick chart; timeframe buttons refetch; indicator buttons toggle MA/VOL/MACD/RSI…; the header live price ticks (crypto immediately, stocks during market hours). (Skip the GUI step if no display; the curl confirms the backend half.)

- [ ] **Step 7: Commit**

```bash
git add front/src/components/ScreenerTable.tsx front/src/components/PortfolioTable.tsx front/src/__tests__/chartWiring.test.tsx
git commit -m "feat(front): clickable tickers open the instrument chart"
```

---

## Self-Review notes

- **Spec coverage:** backend `/charts/{id}` normalize+enrich (Task 1) ↔ spec "Backend — routers/chart.py"; deps + types + api + intervals/openChart/liveCandle (Task 2) ↔ "intervals.ts/openChart.ts/api/useChartData" + naming/proxy; `Chart` + `ChartToolbar` (Task 3) ↔ "components/Chart" + "ChartToolbar"; `ChartView` + routing + live last-candle (Task 4) ↔ "ChartView" + "routing" + "Live"; clickable tickers (Task 5) ↔ "Wiring" + live verify. KLineCharts mocked in tests (canvas-free). Timeframe→eToro mapping, default 1D + MA/VOL, double-nested candle flatten, epoch-ms ascending all covered. ✓
- **Type/name consistency:** `Candle {time,open,high,low,close,volume}` identical backend Pydantic (Task 1) + TS (Task 2) + Chart `toKline` (Task 3) + MSW (Task 2). `ChartResponse` fields match across api/hook/view. `toEtoroInterval`/`TIMEFRAMES` (Task 2) used by ChartToolbar (Task 3) + ChartView (Task 4). `openChart(id)` (Task 2) used by tables (Task 5). `ChartHandle.updateLast` (Task 3) used by ChartView (Task 4). KLineCharts v9 API: `init`/`dispose`/`applyNewData`/`createIndicator(name,isStack,paneOptions)→paneId`/`removeIndicator(paneId,name)`/`updateData`. ✓
- **Placeholders:** none. **Deps:** `klinecharts@^9.8.0`, `react-router-dom@^6.26.0`. **Backward-compat:** existing screener/portfolio/WS untouched; main.tsx now routes (App still default at `/`); existing table tests still green (ticker text unchanged, now inside a button). **Collision:** backend `/charts` vs frontend `/chart` — proxy only forwards `/charts`.
```
