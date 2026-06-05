export interface Timeframe {
  id: string;
  label: string;
  etoro: string;
}

export const TIMEFRAMES: Timeframe[] = [
  { id: "5m", label: "5m", etoro: "FiveMinutes" },
  { id: "15m", label: "15m", etoro: "FifteenMinutes" },
  { id: "1h", label: "1H", etoro: "OneHour" },
  { id: "4h", label: "4H", etoro: "FourHours" },
  { id: "1d", label: "1D", etoro: "OneDay" },
  { id: "1w", label: "1W", etoro: "OneWeek" },
];

export function toEtoroInterval(id: string): string {
  return TIMEFRAMES.find((t) => t.id === id)?.etoro ?? "OneDay";
}
