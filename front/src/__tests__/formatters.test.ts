import { describe, it, expect } from "vitest";
import {
  formatMoney,
  formatPercent,
  formatVolume,
  formatPE,
} from "../lib/formatters";

describe("formatMoney", () => {
  it("formats trillions", () => {
    expect(formatMoney(5_210_000_000_000)).toBe("$5.21T");
  });
  it("formats billions", () => {
    expect(formatMoney(453_000_000_000)).toBe("$453.00B");
  });
  it("formats millions", () => {
    expect(formatMoney(1_200_000)).toBe("$1.20M");
  });
  it("formats small numbers as plain dollars", () => {
    expect(formatMoney(42.5)).toBe("$42.50");
  });
  it("returns em-dash for null/undefined", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney(undefined)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats positive with plus sign", () => {
    expect(formatPercent(1.42)).toBe("+1.42%");
  });
  it("formats negative", () => {
    expect(formatPercent(-3.18)).toBe("-3.18%");
  });
  it("returns em-dash for null", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatVolume", () => {
  it("formats millions", () => {
    expect(formatVolume(169_000_000)).toBe("169M");
  });
  it("formats billions", () => {
    expect(formatVolume(1_200_000_000)).toBe("1.20B");
  });
  it("formats small numbers as-is", () => {
    expect(formatVolume(5_000)).toBe("5,000");
  });
});

describe("formatPE", () => {
  it("rounds to one decimal", () => {
    expect(formatPE(33.456)).toBe("33.5");
  });
  it("em-dash for null", () => {
    expect(formatPE(null)).toBe("—");
  });
});
