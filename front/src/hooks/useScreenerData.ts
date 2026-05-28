import { useQuery } from "@tanstack/react-query";
import { fetchScreener } from "../api/screener";
import type { Universe } from "../types/screener";

export function useScreenerData(universe: Universe) {
  return useQuery({
    queryKey: ["screener", universe],
    queryFn: () => fetchScreener(universe),
    refetchInterval: 60_000,
    staleTime: 60_000,
  });
}
