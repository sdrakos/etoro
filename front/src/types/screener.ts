export type Universe = "sp500" | "nasdaq100" | "combined";

export const UNIVERSES: { id: Universe; label: string }[] = [
  { id: "sp500", label: "S&P 500" },
  { id: "nasdaq100", label: "NASDAQ 100" },
  { id: "combined", label: "Combined" },
];

export interface ScreenerRow {
  ticker: string;
  name: string;
  sector: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
}

export type Category =
  | "stocks" | "crypto" | "etf" | "indices" | "commodities" | "currencies";

export const CATEGORIES: { id: Category; label: string }[] = [
  { id: "stocks", label: "Stocks" },
  { id: "crypto", label: "Crypto" },
  { id: "etf", label: "ETFs" },
  { id: "indices", label: "Indices" },
  { id: "commodities", label: "Commodities" },
  { id: "currencies", label: "Currencies" },
];

export type SortKey = "change" | "name" | "price";

export interface CategoryRow extends ScreenerRow {
  instrument_id: number | null;
  exchange: string | null;
  sell: number | null;
  buy: number | null;
  sentiment_buy_pct: number | null;
  is_open: boolean | null;
}

export interface CategoryPage {
  items: CategoryRow[];
  total: number;
  page: number;
  pageSize: number;
  category: string;
}

export interface CatalogStatus {
  instruments: number;
  last_refresh_age_s: number | null;
}

export interface ExchangeOption {
  exchange: string;
  count: number;
}
