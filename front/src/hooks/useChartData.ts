import { useQuery } from "@tanstack/react-query";
import { fetchChart } from "../api/chart";

export function useChartData(instrumentId: number, interval: string, count = 1000) {
  return useQuery({
    queryKey: ["chart", instrumentId, interval, count],
    queryFn: () => fetchChart(instrumentId, interval, count),
    enabled: Number.isFinite(instrumentId) && instrumentId > 0,
  });
}
