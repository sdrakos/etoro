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
