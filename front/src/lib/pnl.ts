import type { Position } from "../types/portfolio";

export interface PnlResult {
  price: number | null;
  pnlUsd: number | null;
  pnlPct: number | null;
}

export function positionPnl(p: Position, liveLast: number | null | undefined): PnlResult {
  const price = liveLast ?? p.current_rate ?? null;
  if (price === null) return { price: null, pnlUsd: null, pnlPct: null };
  const dir = p.is_buy ? 1 : -1;
  const pnlUsd = p.units * (price - p.open_rate) * dir;
  const pnlPct = p.amount ? (pnlUsd / p.amount) * 100 : null;
  return { price, pnlUsd, pnlPct };
}

export function aggregatePnl(rows: { p: Position; price: number | null }[]) {
  let invested = 0;
  let pnlUsd = 0;
  for (const { p, price } of rows) {
    invested += p.amount;
    if (price !== null) pnlUsd += p.units * (price - p.open_rate) * (p.is_buy ? 1 : -1);
  }
  const pnlPct = invested ? (pnlUsd / invested) * 100 : null;
  return { invested, pnlUsd, pnlPct };
}
