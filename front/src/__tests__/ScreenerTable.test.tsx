import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScreenerTable } from "../components/ScreenerTable";
import type { CategoryRow } from "../types/screener";

const rows: CategoryRow[] = [
  { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
    exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010,
    change_pct: 8.3, sentiment_buy_pct: 90, is_open: true,
    volume: null, market_cap: null, pe_ratio: null },
];

describe("ScreenerTable (eToro columns)", () => {
  it("renders Change/Sell/Buy/Sentiment/Exchange", () => {
    render(<ScreenerTable rows={rows} />);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("Bitcoin")).toBeInTheDocument();
    expect(screen.getByText("Digital Currency")).toBeInTheDocument();
    expect(screen.getByText("+8.30%")).toBeInTheDocument();
    expect(screen.getByText("64990.00")).toBeInTheDocument();
    expect(screen.getByText("65010.00")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();        // sentiment
  });
});
