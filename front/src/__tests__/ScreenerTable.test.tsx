import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScreenerTable } from "../components/ScreenerTable";
import type { ScreenerRow } from "../types/screener";

const ROWS: ScreenerRow[] = [
  {
    ticker: "AAPL", name: "Apple Inc.", sector: "Technology",
    price: 180.0, change_pct: 1.5, volume: 50_000_000,
    market_cap: 2_800_000_000_000, pe_ratio: 28.5,
  },
  {
    ticker: "NVDA", name: "NVIDIA Corp.", sector: "Technology",
    price: 215.33, change_pct: -0.42, volume: 169_000_000,
    market_cap: 5_210_000_000_000, pe_ratio: 33.0,
  },
  {
    ticker: "JPM", name: "JPMorgan Chase", sector: "Financials",
    price: 200.0, change_pct: 0.3, volume: 10_000_000,
    market_cap: 600_000_000_000, pe_ratio: 12.5,
  },
];

describe("ScreenerTable", () => {
  it("renders one row per data item", () => {
    render(<ScreenerTable rows={ROWS} filter="" />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("JPM")).toBeInTheDocument();
  });

  it("renders 8 column headers", () => {
    render(<ScreenerTable rows={ROWS} filter="" />);
    expect(screen.getByRole("columnheader", { name: /ticker/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /name/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /sector/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /price/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /chg/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /volume/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /mkt cap/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /p\/e/i })).toBeInTheDocument();
  });

  it("filters rows by ticker case-insensitively", () => {
    render(<ScreenerTable rows={ROWS} filter="nvd" />);
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByText("JPM")).not.toBeInTheDocument();
  });

  it("filters rows by name substring", () => {
    render(<ScreenerTable rows={ROWS} filter="apple" />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.queryByText("NVDA")).not.toBeInTheDocument();
  });

  it("sorts ascending then descending on header click", async () => {
    const user = userEvent.setup();
    const { container } = render(<ScreenerTable rows={ROWS} filter="" />);
    const priceHeader = screen.getByRole("columnheader", { name: /price/i });

    await user.click(priceHeader);
    let firstRowTicker = container.querySelector("tbody tr:first-child td:first-child")?.textContent;
    expect(firstRowTicker).toBe("AAPL"); // lowest price: 180

    await user.click(priceHeader);
    firstRowTicker = container.querySelector("tbody tr:first-child td:first-child")?.textContent;
    expect(firstRowTicker).toBe("NVDA"); // highest price: 215.33
  });
});
