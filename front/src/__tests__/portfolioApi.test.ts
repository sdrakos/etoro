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
