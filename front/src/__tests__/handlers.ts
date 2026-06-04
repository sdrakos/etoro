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
  http.get("/screener/category/:category", ({ params, request }) => {
    const url = new URL(request.url);
    const category = String(params.category);
    const items = [
      { ticker: "BTC", name: "Bitcoin", sector: "Crypto", instrument_id: 100000,
        exchange: "Digital Currency", price: 65000, sell: 64990, buy: 65010,
        change_pct: 8.3, sentiment_buy_pct: 90, is_open: true,
        volume: null, market_cap: null, pe_ratio: null },
      { ticker: "ABT", name: "Arcblock", sector: "Crypto", instrument_id: 9000,
        exchange: "Digital Currency", price: 0.2, sell: null, buy: null,
        change_pct: -20, sentiment_buy_pct: 30, is_open: true,
        volume: null, market_cap: null, pe_ratio: null },
    ];
    return HttpResponse.json({
      items, total: 2, page: Number(url.searchParams.get("page") ?? 1),
      pageSize: Number(url.searchParams.get("pageSize") ?? 50), category,
      exchange: url.searchParams.get("exchange"),
    });
  }),
  http.get("/screener/exchanges/:category", () =>
    HttpResponse.json([
      { exchange: "Nasdaq", count: 3706 },
      { exchange: "NYSE", count: 2341 },
    ])),
  http.get("/screener/catalog-status", () =>
    HttpResponse.json({ instruments: 15000, last_refresh_age_s: 12 })),
  http.get("/screener/:bad", ({ params }) => {
    if (!["sp500", "nasdaq100", "combined"].includes(params.bad as string)) {
      return new HttpResponse("Not found", { status: 404 });
    }
  }),
];
