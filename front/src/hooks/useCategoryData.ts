import { useQuery } from "@tanstack/react-query";
import { fetchCategory, type CategoryParams } from "../api/screener";
import type { Category } from "../types/screener";

export function useCategoryData(category: Category, params: CategoryParams) {
  return useQuery({
    queryKey: ["screener", "category", category, params],
    queryFn: () => fetchCategory(category, params),
    refetchInterval: 30_000,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}
