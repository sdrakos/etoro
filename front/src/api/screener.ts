import type { ScreenerRow, Universe } from "../types/screener";

export async function fetchScreener(universe: Universe): Promise<ScreenerRow[]> {
  const resp = await fetch(`/screener/${universe}`);
  if (!resp.ok) {
    throw new Error(`Screener fetch failed: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}
