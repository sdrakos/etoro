import { http, HttpResponse } from "msw";
import type { ScreenerRow } from "../types/screener";

const sp500Rows: ScreenerRow[] = [
  { ticker: "AAPL", name: "Apple Inc.", sector: "Technology",
    price: 180, change_pct: 1.5, volume: 50_000_000,
    market_cap: 2.8e12, pe_ratio: 28.5 },
  { ticker: "JPM", name: "JPMorgan Chase", sector: "Financials",
    price: 200, change_pct: 0.3, volume: 10_000_000,
    market_cap: 6e11, pe_ratio: 12.5 },
];

const nasdaq100Rows: ScreenerRow[] = [
  { ticker: "AAPL", name: "Apple Inc.", sector: "Technology",
    price: 180, change_pct: 1.5, volume: 50_000_000,
    market_cap: 2.8e12, pe_ratio: 28.5 },
  { ticker: "TSLA", name: "Tesla Inc.", sector: "Consumer Discretionary",
    price: 250, change_pct: 2.1, volume: 80_000_000,
    market_cap: 8e11, pe_ratio: 75.0 },
];

export const handlers = [
  http.get("/screener/sp500", () => HttpResponse.json(sp500Rows)),
  http.get("/screener/nasdaq100", () => HttpResponse.json(nasdaq100Rows)),
  http.get("/screener/combined", () => HttpResponse.json([
    ...sp500Rows,
    ...nasdaq100Rows.filter(r => r.ticker !== "AAPL"),
  ])),
  http.get("/screener/:bad", ({ params }) => {
    if (!["sp500", "nasdaq100", "combined"].includes(params.bad as string)) {
      return new HttpResponse("Not found", { status: 404 });
    }
  }),
];
