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
