import { useQuery } from "@tanstack/react-query";
import { fetchExchanges } from "../api/screener";
import type { Category } from "../types/screener";

export function useExchanges(category: Category) {
  return useQuery({
    queryKey: ["screener", "exchanges", category],
    queryFn: () => fetchExchanges(category),
    staleTime: 300_000,
  });
}
