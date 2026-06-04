import { useQuery } from "@tanstack/react-query";
import { fetchPortfolio } from "../api/portfolio";

export function usePortfolio() {
  return useQuery({ queryKey: ["portfolio"], queryFn: fetchPortfolio, refetchInterval: 30_000 });
}
