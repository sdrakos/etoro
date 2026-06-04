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
