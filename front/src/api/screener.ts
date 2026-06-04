import type {
  ScreenerRow, Universe, Category, CategoryPage, CatalogStatus, SortKey, ExchangeOption,
} from "../types/screener";

export async function fetchScreener(universe: Universe): Promise<ScreenerRow[]> {
  const resp = await fetch(`/screener/${universe}`);
  if (!resp.ok) throw new Error(`Screener fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}

export interface CategoryParams {
  page?: number;
  pageSize?: number;
  sort?: SortKey;
  dir?: "asc" | "desc";
  q?: string;
  exchange?: string;
}

export async function fetchCategory(
  category: Category, params: CategoryParams = {},
): Promise<CategoryPage> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page ?? 1));
  qs.set("pageSize", String(params.pageSize ?? 50));
  qs.set("sort", params.sort ?? "change");
  qs.set("dir", params.dir ?? "desc");
  if (params.q) qs.set("q", params.q);
  if (params.exchange) qs.set("exchange", params.exchange);
  const resp = await fetch(`/screener/category/${category}?${qs.toString()}`);
  if (!resp.ok) throw new Error(`Category fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function fetchCatalogStatus(): Promise<CatalogStatus> {
  const resp = await fetch(`/screener/catalog-status`);
  if (!resp.ok) throw new Error(`Status fetch failed: ${resp.status}`);
  return resp.json();
}

export async function fetchExchanges(category: Category): Promise<ExchangeOption[]> {
  const resp = await fetch(`/screener/exchanges/${category}`);
  if (!resp.ok) throw new Error(`Exchanges fetch failed: ${resp.status} ${resp.statusText}`);
  return resp.json();
}
