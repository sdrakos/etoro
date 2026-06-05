import type { Candle } from "../types/chart";

/** Merge a live price into the last candle: set close, extend high/low. */
export function liveCandle(last: Candle, price: number): Candle {
  return {
    ...last,
    close: price,
    high: Math.max(last.high, price),
    low: Math.min(last.low, price),
  };
}
