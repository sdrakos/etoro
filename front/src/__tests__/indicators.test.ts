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
