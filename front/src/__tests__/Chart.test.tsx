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
