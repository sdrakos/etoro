import type { PortfolioResponse } from "../types/portfolio";

export async function fetchPortfolio(): Promise<PortfolioResponse> {
  const resp = await fetch("/portfolio/positions");
  if (!resp.ok) throw new Error(`Portfolio fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function closePosition(
  positionId: number, body: { InstrumentID: number; UnitsToDeduct?: number },
): Promise<unknown> {
  const resp = await fetch(`/portfolio/close/${positionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Close failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}
