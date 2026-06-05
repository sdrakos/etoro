import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScreenerTable } from "../components/ScreenerTable";
import { PortfolioTable } from "../components/PortfolioTable";
import { openChart } from "../lib/openChart";
import type { CategoryRow } from "../types/screener";
import type { Position } from "../types/portfolio";

vi.mock("../lib/openChart", () => ({ openChart: vi.fn() }));

const srow: CategoryRow = { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
  exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010, change_pct: 8.3,
  sentiment_buy_pct: 90, is_open: true, volume: null, market_cap: null, pe_ratio: null };
const prow: Position = { position_id: 111, instrument_id: 1137, symbol: "NVDA", name: "NVIDIA",
  is_buy: true, units: 2, open_rate: 100, amount: 200, leverage: 1, current_rate: 110 };

describe("chart wiring", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("ScreenerTable ticker opens the chart", async () => {
    render(<ScreenerTable rows={[srow]} />);
    await userEvent.click(screen.getByRole("button", { name: "BTC" }));
    expect(openChart).toHaveBeenCalledWith(100000);
  });

  it("PortfolioTable symbol opens the chart", async () => {
    render(<PortfolioTable rows={[prow]} ticks={new Map()} onClose={() => {}} closingId={null} />);
    await userEvent.click(screen.getByRole("button", { name: "NVDA" }));
    expect(openChart).toHaveBeenCalledWith(1137);
  });
});
