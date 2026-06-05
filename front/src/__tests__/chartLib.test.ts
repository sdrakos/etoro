import { describe, it, expect, vi, beforeEach } from "vitest";
import { toEtoroInterval, countFor, TIMEFRAMES } from "../lib/intervals";
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

  it("gives a per-interval candle count (deep history on 1d/1w), default 1000", () => {
    expect(countFor("1d")).toBe(1000);   // ~4 years (eToro daily cap)
    expect(countFor("1w")).toBe(1000);   // full history → 2007/2012
    expect(countFor("5m")).toBe(500);
    expect(countFor("nonsense")).toBe(1000);
    expect(TIMEFRAMES.every((t) => typeof t.count === "number")).toBe(true);
  });
});

describe("fetchChart count param", () => {
  it("puts the count in the querystring", async () => {
    const r = await fetchChart(1001, "OneWeek", 1000);
    expect(r.candles.length).toBeGreaterThan(0);
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
