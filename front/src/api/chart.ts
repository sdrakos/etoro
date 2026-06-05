import type { ChartResponse } from "../types/chart";

export async function fetchChart(instrumentId: number, interval: string): Promise<ChartResponse> {
  const qs = new URLSearchParams({ interval, count: "300" });
  const resp = await fetch(`/charts/${instrumentId}?${qs.toString()}`);
  if (!resp.ok) throw new Error(`Chart fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}
