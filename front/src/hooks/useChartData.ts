import { useQuery } from "@tanstack/react-query";
import { fetchChart } from "../api/chart";

export function useChartData(instrumentId: number, interval: string) {
  return useQuery({
    queryKey: ["chart", instrumentId, interval],
    queryFn: () => fetchChart(instrumentId, interval),
    enabled: Number.isFinite(instrumentId) && instrumentId > 0,
  });
}
