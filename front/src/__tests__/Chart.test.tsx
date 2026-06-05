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
