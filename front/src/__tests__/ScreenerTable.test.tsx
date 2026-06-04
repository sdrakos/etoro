import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScreenerTable } from "../components/ScreenerTable";
import type { CategoryRow } from "../types/screener";
import type { LiveTick } from "../hooks/usePriceStream";

const rows: CategoryRow[] = [
  { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
    exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010,
    change_pct: 8.3, sentiment_buy_pct: 90, is_open: true,
    volume: null, market_cap: null, pe_ratio: null },
];

describe("ScreenerTable (eToro columns)", () => {
  it("renders seed values when no ticks", () => {
    render(<ScreenerTable rows={rows} />);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("Bitcoin")).toBeInTheDocument();
    expect(screen.getByText("Digital Currency")).toBeInTheDocument();
    expect(screen.getByText("+8.30%")).toBeInTheDocument();
    expect(screen.getByText("64990.00")).toBeInTheDocument();
    expect(screen.getByText("65010.00")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
  });

  it("overlays a live tick (sell=bid, buy=ask, change)", () => {
    const ticks = new Map<number, LiveTick>([
      [100000, { bid: 70000, ask: 70010, last: 70005, change_pct: -2.5, ts: "T" }],
    ]);
    render(<ScreenerTable rows={rows} ticks={ticks} />);
    expect(screen.getByText("70000.00")).toBeInTheDocument();   // sell ← bid
    expect(screen.getByText("70010.00")).toBeInTheDocument();   // buy ← ask
    expect(screen.getByText("-2.50%")).toBeInTheDocument();     // live change
  });
});
