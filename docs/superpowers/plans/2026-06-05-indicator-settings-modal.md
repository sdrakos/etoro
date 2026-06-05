# Per-indicator settings modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each active TA indicator a ⚙️ that opens a TradingView-style modal to edit its parameters (calcParams) and line colors, applied live to the KLineCharts chart.

**Architecture:** The indicator model changes from `string` to `IndicatorConfig {name, calcParams, colors}`. A new `IndicatorSettingsModal` (Inputs + Style tabs) edits a config; `ChartView` holds a `Map<name,config>`; `Chart.tsx` creates indicators with `calcParams`/`styles` and calls `overrideIndicator` when a config changes.

**Tech Stack:** React + KLineCharts v9 (`createIndicator`/`overrideIndicator` already support `calcParams`/`styles`) + Vitest. No backend, no new deps.

Frontend from `etoro/front/`. Clean commits, **no** Co-Authored-By trailer. Branch `feat/yahoo-data-source` (controller syncs `main` after each task).

**Design source:** `docs/superpowers/specs/2026-06-05-indicator-settings-modal-design.md`.

**Ordering note:** Task 4 changes `Chart`'s prop from `string[]` → `IndicatorConfig[]`, which makes `ChartView` (still passing strings) type-mismatch — so `npm run build` is **red between Task 4 and Task 5** (Task 5 rewrites ChartView). Task 4 does NOT run the build; Task 5 makes it green. `ChartToolbar`'s new prop is **optional**, so Task 3 does not break anything.

---

## File Structure

| File | Responsibility |
|---|---|
| `front/src/lib/indicators.ts` | `IndicatorConfig`, defaults, `defaultConfig`, `paramLabels`, `klineStyles`, `INDICATORS` |
| `front/src/components/IndicatorSettingsModal.tsx` | the modal (Inputs + Style tabs, live-apply, reset) |
| `front/src/components/ChartToolbar.tsx` | + optional `onOpenSettings` + ⚙️ per active indicator |
| `front/src/components/Chart.tsx` | `indicators: IndicatorConfig[]` → create with params+styles, `overrideIndicator` on change |
| `front/src/views/ChartView.tsx` | `Map<name,config>` state + `settingsFor` + modal wiring |
| `front/src/__tests__/*` | indicators, modal; updated Chart + ChartToolbar tests |

---

### Task 1: `lib/indicators.ts`

**Files:**
- Create: `front/src/lib/indicators.ts`, `front/src/__tests__/indicators.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// front/src/__tests__/indicators.test.ts
import { describe, it, expect } from "vitest";
import { defaultConfig, paramLabels, klineStyles, INDICATORS } from "../lib/indicators";

describe("indicators", () => {
  it("defaultConfig returns params+colors and is a deep clone", () => {
    expect(defaultConfig("MACD")).toEqual({
      name: "MACD", calcParams: [12, 26, 9], colors: ["#EFB90B", "#935EBD"],
    });
    const a = defaultConfig("MA");
    a.calcParams[0] = 999;
    a.colors[0] = "#000000";
    expect(defaultConfig("MA").calcParams[0]).toBe(5);      // defaults not mutated
    expect(defaultConfig("MA").colors[0]).toBe("#EFB90B");
  });

  it("paramLabels + klineStyles + INDICATORS", () => {
    expect(paramLabels("RSI")).toEqual(["RSI1", "RSI2", "RSI3"]);
    expect(paramLabels("MACD")).toEqual(["Short", "Long", "Signal"]);
    expect(klineStyles(["#f00", "#0f0"])).toEqual({ lines: [{ color: "#f00" }, { color: "#0f0" }] });
    expect(INDICATORS).toContain("KDJ");
    expect(INDICATORS).toHaveLength(7);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- indicators`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `front/src/lib/indicators.ts`**

```typescript
export interface IndicatorConfig {
  name: string;
  calcParams: number[];
  colors: string[];   // one color per drawn line (may differ from calcParams.length)
}

interface IndicatorDef {
  calcParams: number[];
  labels: string[];
  colors: string[];
}

// Distinct, theme-friendly line palette.
const PALETTE = ["#EFB90B", "#935EBD", "#2962FF", "#E5436F"];

const DEFS: Record<string, IndicatorDef> = {
  MA: { calcParams: [5, 10, 30, 60], labels: ["MA1", "MA2", "MA3", "MA4"], colors: PALETTE.slice(0, 4) },
  EMA: { calcParams: [6, 12, 20], labels: ["EMA1", "EMA2", "EMA3"], colors: PALETTE.slice(0, 3) },
  BOLL: { calcParams: [20, 2], labels: ["Period", "StdDev"], colors: PALETTE.slice(0, 3) },
  VOL: { calcParams: [5, 10, 20], labels: ["MA1", "MA2", "MA3"], colors: PALETTE.slice(0, 3) },
  MACD: { calcParams: [12, 26, 9], labels: ["Short", "Long", "Signal"], colors: PALETTE.slice(0, 2) },
  RSI: { calcParams: [6, 12, 24], labels: ["RSI1", "RSI2", "RSI3"], colors: PALETTE.slice(0, 3) },
  KDJ: { calcParams: [9, 3, 3], labels: ["K", "D", "J"], colors: PALETTE.slice(0, 3) },
};

export const INDICATORS = ["MA", "EMA", "BOLL", "VOL", "MACD", "RSI", "KDJ"] as const;

export function defaultConfig(name: string): IndicatorConfig {
  const d = DEFS[name] ?? { calcParams: [], labels: [], colors: [] };
  return { name, calcParams: [...d.calcParams], colors: [...d.colors] };
}

export function paramLabels(name: string): string[] {
  return DEFS[name]?.labels ?? [];
}

export function klineStyles(colors: string[]): { lines: { color: string }[] } {
  return { lines: colors.map((color) => ({ color })) };
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- indicators` → PASS. Then full suite `npm run test:run` → all pass.

- [ ] **Step 5: Commit**

```bash
git add front/src/lib/indicators.ts front/src/__tests__/indicators.test.ts
git commit -m "feat(chart): indicator config model + defaults (params/colors/labels)"
```

---

### Task 2: `IndicatorSettingsModal`

**Files:**
- Create: `front/src/components/IndicatorSettingsModal.tsx`, `front/src/__tests__/IndicatorSettingsModal.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// front/src/__tests__/IndicatorSettingsModal.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IndicatorSettingsModal } from "../components/IndicatorSettingsModal";
import type { IndicatorConfig } from "../lib/indicators";

const cfg: IndicatorConfig = { name: "RSI", calcParams: [6, 12, 24], colors: ["#aaaaaa", "#bbbbbb", "#cccccc"] };

function setup() {
  const onApply = vi.fn();
  const onReset = vi.fn();
  const onClose = vi.fn();
  render(<IndicatorSettingsModal name="RSI" config={cfg} onApply={onApply} onReset={onReset} onClose={onClose} />);
  return { onApply, onReset, onClose };
}

describe("IndicatorSettingsModal", () => {
  it("renders one number input per calcParam and applies edits", () => {
    const { onApply } = setup();
    const inputs = screen.getAllByRole("spinbutton");
    expect(inputs).toHaveLength(3);
    fireEvent.change(inputs[0], { target: { value: "9" } });
    expect(onApply).toHaveBeenLastCalledWith({ name: "RSI", calcParams: [9, 12, 24], colors: cfg.colors });
  });

  it("switches to the Style tab and edits a color", async () => {
    const { onApply } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Style" }));
    const color = screen.getByLabelText("Line 1 color");
    fireEvent.change(color, { target: { value: "#ff0000" } });
    expect(onApply).toHaveBeenLastCalledWith(
      { name: "RSI", calcParams: cfg.calcParams, colors: ["#ff0000", "#bbbbbb", "#cccccc"] });
  });

  it("fires reset and close", async () => {
    const { onReset, onClose } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Reset to defaults" }));
    expect(onReset).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- IndicatorSettingsModal`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `front/src/components/IndicatorSettingsModal.tsx`**

```tsx
import { useEffect, useState } from "react";
import { paramLabels, type IndicatorConfig } from "../lib/indicators";

interface Props {
  name: string;
  config: IndicatorConfig;
  onApply: (c: IndicatorConfig) => void;
  onReset: () => void;
  onClose: () => void;
}

const tabBtn =
  "rounded-t-md px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70";

export function IndicatorSettingsModal({ name, config, onApply, onReset, onClose }: Props) {
  const [tab, setTab] = useState<"inputs" | "style">("inputs");
  const labels = paramLabels(name);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const setParam = (i: number, v: number) =>
    onApply({ ...config, calcParams: config.calcParams.map((p, idx) => (idx === i ? v : p)) });
  const setColor = (i: number, v: string) =>
    onApply({ ...config, colors: config.colors.map((c, idx) => (idx === i ? v : c)) });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-label={`${name} settings`}
      onClick={onClose}
    >
      <div
        className="w-80 rounded-xl border border-border-default bg-bg-base shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
          <h2 className="font-semibold">{name} settings</h2>
          <button type="button" aria-label="Close" onClick={onClose}
            className="text-fg-muted hover:text-fg-default">✕</button>
        </div>

        <div className="flex gap-1 border-b border-border-default px-4 pt-2">
          {(["inputs", "style"] as const).map((t) => (
            <button key={t} type="button" aria-pressed={tab === t} onClick={() => setTab(t)}
              className={[tabBtn, tab === t ? "bg-bg-hover text-fg-default"
                : "text-fg-muted hover:text-fg-default"].join(" ")}>
              {t === "inputs" ? "Inputs" : "Style"}
            </button>
          ))}
        </div>

        <div className="space-y-3 px-4 py-4">
          {tab === "inputs"
            ? config.calcParams.map((p, i) => (
                <label key={i} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-fg-muted">{labels[i] ?? `Param ${i + 1}`}</span>
                  <input
                    type="number"
                    min={1}
                    value={p}
                    onChange={(e) => setParam(i, Number(e.target.value))}
                    className="w-24 rounded border border-border-default bg-bg-surface px-2 py-1 text-right tabular-nums"
                  />
                </label>
              ))
            : config.colors.map((c, i) => (
                <label key={i} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-fg-muted">Line {i + 1}</span>
                  <input
                    type="color"
                    aria-label={`Line ${i + 1} color`}
                    value={c}
                    onChange={(e) => setColor(i, e.target.value)}
                    className="h-7 w-12 rounded border border-border-default bg-transparent"
                  />
                </label>
              ))}
        </div>

        <div className="flex items-center justify-between border-t border-border-default px-4 py-3">
          <button type="button" onClick={onReset}
            className="text-sm text-fg-muted hover:text-fg-default">Reset to defaults</button>
          <button type="button" onClick={onClose}
            className="rounded-md bg-accent-blue px-3 py-1.5 text-sm font-medium text-white">Done</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- IndicatorSettingsModal` → PASS (3). Then full suite `npm run test:run` → all pass.

- [ ] **Step 5: Commit**

```bash
git add front/src/components/IndicatorSettingsModal.tsx front/src/__tests__/IndicatorSettingsModal.test.tsx
git commit -m "feat(chart): IndicatorSettingsModal (Inputs + Style tabs, live-apply)"
```

---

### Task 3: `ChartToolbar` — per-indicator ⚙️

**Files:**
- Modify: `front/src/components/ChartToolbar.tsx`, `front/src/__tests__/ChartToolbar.test.tsx`

- [ ] **Step 1: Replace `front/src/__tests__/ChartToolbar.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChartToolbar } from "../components/ChartToolbar";

describe("ChartToolbar", () => {
  it("renders timeframes + indicators, gears for active, and fires callbacks", async () => {
    const onTimeframe = vi.fn();
    const onToggle = vi.fn();
    const onOpenSettings = vi.fn();
    render(<ChartToolbar timeframe="1d" onTimeframe={onTimeframe}
      active={new Set(["MA", "VOL"])} onToggle={onToggle} onOpenSettings={onOpenSettings} />);

    expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "1H" }));
    expect(onTimeframe).toHaveBeenCalledWith("1h");

    await userEvent.click(screen.getByRole("button", { name: "RSI" }));   // inactive → toggle only
    expect(onToggle).toHaveBeenCalledWith("RSI");

    // active indicators expose a settings gear; inactive ones don't
    expect(screen.queryByRole("button", { name: "RSI settings" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "MA settings" }));
    expect(onOpenSettings).toHaveBeenCalledWith("MA");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- ChartToolbar`
Expected: FAIL — no `onOpenSettings` / no "MA settings" gear button.

- [ ] **Step 3: Replace `front/src/components/ChartToolbar.tsx`**

```tsx
import { TIMEFRAMES } from "../lib/intervals";

const INDICATORS = ["MA", "EMA", "BOLL", "VOL", "MACD", "RSI", "KDJ"];

interface Props {
  timeframe: string;
  onTimeframe: (id: string) => void;
  active: Set<string>;
  onToggle: (name: string) => void;
  onOpenSettings?: (name: string) => void;
}

const btn =
  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors outline-none " +
  "focus-visible:ring-2 focus-visible:ring-accent-blue/70";

export function ChartToolbar({ timeframe, onTimeframe, active, onToggle, onOpenSettings }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border-default px-4 py-2">
      <div className="flex gap-1">
        {TIMEFRAMES.map((t) => (
          <button key={t.id} type="button" aria-pressed={t.id === timeframe}
            onClick={() => onTimeframe(t.id)}
            className={[btn, t.id === timeframe ? "bg-accent-blue text-white"
              : "text-fg-muted hover:text-fg-default hover:bg-bg-hover"].join(" ")}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-1">
        {INDICATORS.map((n) => (
          <span key={n} className="inline-flex items-center">
            <button type="button" aria-pressed={active.has(n)} onClick={() => onToggle(n)}
              className={[btn, active.has(n) ? "bg-bg-hover text-fg-default"
                : "text-fg-muted hover:text-fg-default hover:bg-bg-hover/60"].join(" ")}>
              {n}
            </button>
            {active.has(n) && onOpenSettings && (
              <button type="button" aria-label={`${n} settings`} onClick={() => onOpenSettings(n)}
                className="ml-0.5 rounded px-1 py-1 text-xs leading-none text-fg-muted hover:text-fg-default outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70">
                ⚙
              </button>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- ChartToolbar` → PASS. Then full suite `npm run test:run` → all pass (the new prop is optional, so nothing else breaks).

- [ ] **Step 5: Commit**

```bash
git add front/src/components/ChartToolbar.tsx front/src/__tests__/ChartToolbar.test.tsx
git commit -m "feat(chart): per-active-indicator settings gear in the toolbar"
```

---

### Task 4: `Chart.tsx` — config props + `overrideIndicator`

**Files:**
- Modify: `front/src/components/Chart.tsx`, `front/src/__tests__/Chart.test.tsx`

- [ ] **Step 1: Replace `front/src/__tests__/Chart.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { init } from "klinecharts";
import { Chart } from "../components/Chart";
import type { Candle } from "../types/chart";
import type { IndicatorConfig } from "../lib/indicators";

vi.mock("klinecharts", () => {
  const chart = {
    applyNewData: vi.fn(),
    createIndicator: vi.fn(() => "pane_1"),
    overrideIndicator: vi.fn(),
    removeIndicator: vi.fn(),
    updateData: vi.fn(),
  };
  return { init: vi.fn(() => chart), dispose: vi.fn() };
});

const candles: Candle[] = [{ time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }];
const cfg = (name: string, calcParams: number[], colors: string[]): IndicatorConfig => ({ name, calcParams, colors });

describe("Chart", () => {
  it("creates indicators with calcParams + styles", () => {
    render(<Chart candles={candles} indicators={[cfg("MA", [5, 10], ["#fff", "#000"]), cfg("VOL", [5], ["#abc"])]} />);
    const chart = (init as unknown as { mock: { results: { value: any }[] } }).mock.results[0].value;
    const values = chart.createIndicator.mock.calls.map((c: any[]) => c[0]);
    const ma = values.find((v: any) => v.name === "MA");
    expect(ma).toEqual({ name: "MA", calcParams: [5, 10], styles: { lines: [{ color: "#fff" }, { color: "#000" }] } });
    expect(values.some((v: any) => v.name === "VOL")).toBe(true);
  });

  it("overrideIndicator runs when a config's params change", () => {
    const { rerender } = render(<Chart candles={candles} indicators={[cfg("RSI", [6], ["#f00"])]} />);
    const chart = (init as unknown as { mock: { results: { value: any }[] } }).mock.results[0].value;
    rerender(<Chart candles={candles} indicators={[cfg("RSI", [21], ["#f00"])]} />);
    const last = chart.overrideIndicator.mock.calls.at(-1);
    expect(last[0]).toEqual({ name: "RSI", calcParams: [21], styles: { lines: [{ color: "#f00" }] } });
    expect(last[1]).toBe("pane_1");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `front/`): `npm run test:run -- Chart`
Expected: FAIL — `Chart` still takes `string[]` and never calls `overrideIndicator`.

- [ ] **Step 3: Replace `front/src/components/Chart.tsx`**

```tsx
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { init, dispose } from "klinecharts";
import type { Candle } from "../types/chart";
import { klineStyles, type IndicatorConfig } from "../lib/indicators";

export interface ChartHandle {
  updateLast: (c: Candle) => void;
}

interface Props {
  candles: Candle[];
  indicators: IndicatorConfig[];
}

const MAIN_OVERLAYS = ["MA", "EMA", "BOLL"];

function toKline(c: Candle) {
  return { timestamp: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
           volume: c.volume ?? undefined };
}

export const Chart = forwardRef<ChartHandle, Props>(function Chart({ candles, indicators }, ref) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof init> | null>(null);
  const tracked = useRef<Map<string, { paneId: string; sig: string }>>(new Map());

  useEffect(() => {
    chartRef.current = init(elRef.current!);
    return () => {
      if (elRef.current) dispose(elRef.current);
      chartRef.current = null;
      tracked.current.clear();
    };
  }, []);

  useEffect(() => {
    chartRef.current?.applyNewData(candles.map(toKline));
  }, [candles]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const byName = new Map(indicators.map((i) => [i.name, i]));

    for (const [name, info] of [...tracked.current]) {
      if (!byName.has(name)) {
        chart.removeIndicator(info.paneId, name);
        tracked.current.delete(name);
      }
    }

    for (const cfg of indicators) {
      const value = { name: cfg.name, calcParams: cfg.calcParams, styles: klineStyles(cfg.colors) };
      const sig = JSON.stringify({ p: cfg.calcParams, c: cfg.colors });
      const existing = tracked.current.get(cfg.name);
      if (!existing) {
        const paneId = MAIN_OVERLAYS.includes(cfg.name)
          ? chart.createIndicator(value, false, { id: "candle_pane" })
          : chart.createIndicator(value);
        if (paneId) tracked.current.set(cfg.name, { paneId, sig });
      } else if (existing.sig !== sig) {
        chart.overrideIndicator(value, existing.paneId);
        tracked.current.set(cfg.name, { paneId: existing.paneId, sig });
      }
    }
  }, [indicators]);

  useImperativeHandle(ref, () => ({
    updateLast: (c) => chartRef.current?.updateData(toKline(c)),
  }), []);

  return <div ref={elRef} className="h-full w-full" />;
});
```

- [ ] **Step 4: Run to verify it passes**

Run (from `front/`): `npm run test:run -- Chart` → PASS (2).
Do **NOT** run `npm run build` here — `ChartView` still passes `string[]` to `Chart`, so `tsc` is red until Task 5. (You may run the full vitest suite; the `ChartView` test renders fine through the mocked KLineCharts even with the temporary mismatch, but if it errors, that's expected and fixed in Task 5 — note it and proceed.)

- [ ] **Step 5: Commit**

```bash
git add front/src/components/Chart.tsx front/src/__tests__/Chart.test.tsx
git commit -m "feat(chart): Chart takes indicator configs + overrideIndicator on change"
```

---

### Task 5: `ChartView` wiring + full verify

**Files:**
- Modify: `front/src/views/ChartView.tsx`
- Test: existing `front/src/__tests__/ChartView.test.tsx` (must stay green)

- [ ] **Step 1: Replace `front/src/views/ChartView.tsx`**

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useChartData } from "../hooks/useChartData";
import { usePriceStream } from "../hooks/usePriceStream";
import { Chart, type ChartHandle } from "../components/Chart";
import { ChartToolbar } from "../components/ChartToolbar";
import { IndicatorSettingsModal } from "../components/IndicatorSettingsModal";
import { toEtoroInterval, countFor } from "../lib/intervals";
import { defaultConfig, type IndicatorConfig } from "../lib/indicators";
import { liveCandle } from "../lib/chartLive";

export function ChartView() {
  const { instrumentId } = useParams();
  const id = Number(instrumentId);
  const [tf, setTf] = useState("1d");
  const [configs, setConfigs] = useState<Map<string, IndicatorConfig>>(
    () => new Map([["MA", defaultConfig("MA")], ["VOL", defaultConfig("VOL")]]),
  );
  const [settingsFor, setSettingsFor] = useState<string | null>(null);

  const { data, isLoading, isError } = useChartData(id, toEtoroInterval(tf), countFor(tf));
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

  const toggle = (name: string) => {
    setConfigs((prev) => {
      const next = new Map(prev);
      if (next.has(name)) next.delete(name);
      else next.set(name, defaultConfig(name));
      return next;
    });
    setSettingsFor((cur) => (cur === name ? null : cur));
  };
  const applyConfig = (name: string, cfg: IndicatorConfig) =>
    setConfigs((prev) => new Map(prev).set(name, cfg));

  const indicators = useMemo(() => [...configs.values()], [configs]);
  const active = useMemo(() => new Set(configs.keys()), [configs]);
  const livePrice = stream.ticks.get(id)?.last;
  const editing = settingsFor ? configs.get(settingsFor) : undefined;

  return (
    <div className="flex h-screen flex-col bg-bg-base text-fg-default">
      <header className="flex items-baseline gap-3 border-b border-border-default px-4 py-3">
        <span className="font-mono text-lg font-semibold">{data?.symbol ?? `#${id}`}</span>
        {data?.name && <span className="text-sm text-fg-muted">{data.name}</span>}
        {livePrice != null && (
          <span className="ml-auto font-mono tabular-nums text-accent-green">{livePrice.toFixed(2)}</span>
        )}
      </header>
      <ChartToolbar timeframe={tf} onTimeframe={setTf} active={active} onToggle={toggle}
        onOpenSettings={setSettingsFor} />
      <main className="relative flex-1">
        {isLoading && <p className="p-4 text-fg-muted">Loading chart…</p>}
        {isError && (
          <p className="p-4 text-accent-red">Could not load chart. Is the backend running on :8765?</p>
        )}
        {data && candles.length === 0 && (
          <p className="p-4 text-fg-muted">No chart data for this instrument.</p>
        )}
        {data && candles.length > 0 && (
          <Chart ref={chartRef} candles={candles} indicators={indicators} />
        )}
      </main>
      {settingsFor && editing && (
        <IndicatorSettingsModal
          name={settingsFor}
          config={editing}
          onApply={(c) => applyConfig(settingsFor, c)}
          onReset={() => applyConfig(settingsFor, defaultConfig(settingsFor))}
          onClose={() => setSettingsFor(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run the full suite + build**

Run (from `front/`): `npm run test:run` → all PASS (the existing `ChartView.test` still asserts the AAPL header + "1D" button; KLineCharts is mocked). Then `npm run build` (`tsc -b && vite build`) → **clean** now (ChartView passes `IndicatorConfig[]` to Chart). If a type error remains, fix it minimally.

- [ ] **Step 3: Manual/live verify (frontend dev — user-managed backend on 8765)**

Frontend (`cd front && npm run dev`): open a chart (click a ticker). Active indicators (MA, VOL) show a ⚙️ in the toolbar; click it → modal opens with **Inputs** (MA1/MA2/MA3/MA4 numbers) and **Style** (color pickers). Change a period or color → the chart **updates instantly**. Toggle RSI on → its ⚙️ appears; open it, set RSI period → the RSI sub-pane reflects it. "Reset to defaults" restores; Esc/✕/Done close. (No backend change — nothing to curl; this is a pure-frontend feature.)

- [ ] **Step 4: Commit**

```bash
git add front/src/views/ChartView.tsx
git commit -m "feat(chart): wire per-indicator settings modal into the chart view"
```

---

## Self-Review notes

- **Spec coverage:** config model + defaults (Task 1) ↔ spec "Indicator model"; modal Inputs+Style+live-apply+reset (Task 2) ↔ "IndicatorSettingsModal"; per-active ⚙️ (Task 3) ↔ "ChartToolbar"; create-with-params + `overrideIndicator` on change (Task 4) ↔ "Chart.tsx"; `Map<name,config>` + `settingsFor` + modal wiring (Task 5) ↔ "ChartView" + "Data flow". Esc/click-outside/aria on the modal; colors independent of calcParams count; KLineCharts `createIndicator({name,calcParams,styles})` / `overrideIndicator(value, paneId)`. ✓
- **Type/name consistency:** `IndicatorConfig {name, calcParams, colors}` defined Task 1, used Tasks 2–5; `defaultConfig`/`paramLabels`/`klineStyles` (Task 1) used by modal (Task 2), Chart (Task 4), ChartView (Task 5); `ChartToolbar` `onOpenSettings?` (Task 3) supplied by ChartView (Task 5); modal props `{name, config, onApply, onReset, onClose}` match the ChartView render. ✓
- **Placeholders:** none. **Deps:** none new. **Ordering/red window:** Task 4 changes `Chart`'s prop type; `npm run build` is red only between Task 4 and Task 5 (Task 4 skips build, Task 5 restores green). `ChartToolbar`'s new prop is optional so Task 3 is non-breaking. **Backward-compat:** chart data/endpoint/relay untouched; only the in-memory indicator model changes.
```
