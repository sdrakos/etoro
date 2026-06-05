export interface Timeframe {
  id: string;
  label: string;
  etoro: string;
  /** How many candles to request for this timeframe (eToro caps ~1000). */
  count: number;
}

// eToro caps daily at ~1000 candles (~4y) and serves weekly back to 2007/2012.
// Intraday is naturally short, so smaller counts keep loads snappy.
export const TIMEFRAMES: Timeframe[] = [
  { id: "5m", label: "5m", etoro: "FiveMinutes", count: 500 },     // ~1.7 days
  { id: "15m", label: "15m", etoro: "FifteenMinutes", count: 700 }, // ~7 days
  { id: "1h", label: "1H", etoro: "OneHour", count: 1000 },         // ~40 days
  { id: "4h", label: "4H", etoro: "FourHours", count: 1000 },       // ~160 days
  { id: "1d", label: "1D", etoro: "OneDay", count: 1000 },          // ~4 years
  { id: "1w", label: "1W", etoro: "OneWeek", count: 1000 },         // full history
];

export function toEtoroInterval(id: string): string {
  return TIMEFRAMES.find((t) => t.id === id)?.etoro ?? "OneDay";
}

export function countFor(id: string): number {
  return TIMEFRAMES.find((t) => t.id === id)?.count ?? 1000;
}
