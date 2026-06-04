import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PortfolioTable } from "../components/PortfolioTable";
import type { Position } from "../types/portfolio";
import type { LiveTick } from "../hooks/usePriceStream";

const rows: Position[] = [
  { position_id: 111, instrument_id: 1137, symbol: "ETH", name: "Ethereum",
    is_buy: true, units: 2, open_rate: 100, amount: 200, leverage: 1, current_rate: 110 },
];

describe("PortfolioTable", () => {
  it("renders a position with live P&L and fires onClose", async () => {
    const onClose = vi.fn();
    const ticks = new Map<number, LiveTick>([
      [1137, { bid: null, ask: null, last: 120, change_pct: null, ts: "T" }],
    ]);
    render(<PortfolioTable rows={rows} ticks={ticks} onClose={onClose} closingId={null} />);
    expect(screen.getByText("ETH")).toBeInTheDocument();
    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText("120.00")).toBeInTheDocument();
    expect(screen.getByText("+40.00")).toBeInTheDocument();   // pnl$ = 2*(120-100)
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledWith(rows[0]);
  });
});
