import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCategoryData } from "./hooks/useCategoryData";
import { usePriceStream } from "./hooks/usePriceStream";
import { fetchCatalogStatus } from "./api/screener";
import { CategoryTabs } from "./components/CategoryTabs";
import { SearchBox } from "./components/SearchBox";
import { ScreenerTable } from "./components/ScreenerTable";
import { Pagination } from "./components/Pagination";
import { CATEGORIES, type Category, type SortKey } from "./types/screener";

const PAGE_SIZE = 50;

const SORTS: { id: SortKey; label: string }[] = [
  { id: "change", label: "Change %" },
  { id: "name", label: "Name" },
  { id: "price", label: "Price" },
];

/** Humanise the catalog freshness age into a compact "updated Ns/m ago" string. */
function freshness(ageS: number | null | undefined): string {
  if (ageS === null || ageS === undefined) return "live";
  const s = Math.max(0, Math.round(ageS));
  if (s < 60) return `updated ${s}s ago`;
  const m = Math.round(s / 60);
  return `updated ${m}m ago`;
}

/** Content-shaped placeholder so the layout doesn't jump when rows arrive. */
function TableSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="h-full overflow-hidden rounded-xl border border-border-default bg-bg-base shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.6)]"
    >
      <div className="border-b border-border-default px-4 py-3">
        <div className="h-3 w-24 rounded bg-bg-surface" />
      </div>
      <div className="divide-y divide-border-default/40">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-4 px-4 py-3"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-bg-hover" />
            <span className="h-3 w-14 animate-pulse rounded bg-bg-surface" />
            <span className="h-3 w-40 animate-pulse rounded bg-bg-surface/70" />
            <span className="ml-auto h-3 w-16 animate-pulse rounded bg-bg-surface" />
            <span className="h-3 w-12 animate-pulse rounded bg-bg-surface/70" />
            <span className="h-1.5 w-20 animate-pulse rounded-full bg-bg-surface" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [category, setCategory] = useState<Category>("stocks");
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("change");

  const { data, isLoading, isError, isFetching, refetch } = useCategoryData(
    category,
    { page, pageSize: PAGE_SIZE, sort, dir: "desc", q: q || undefined },
  );

  const status = useQuery({
    queryKey: ["catalog-status"],
    queryFn: fetchCatalogStatus,
    refetchInterval: 30_000,
  });

  const stream = usePriceStream();
  useEffect(() => {
    const ids = (data?.items ?? [])
      .map((r) => r.instrument_id)
      .filter((x): x is number => typeof x === "number");
    if (ids.length) stream.subscribe(ids);
  }, [data, stream]);

  // Stable identities: SearchBox debounces on `onSearch` in an effect, so a
  // fresh closure each render (e.g. on every 30s poll tick) would needlessly
  // re-arm the timer. useCallback keeps the handlers referentially stable.
  const onCategory = useCallback((c: Category) => {
    setCategory(c);
    setPage(1);
  }, []);
  const onSearch = useCallback((s: string) => {
    setQ(s);
    setPage(1);
  }, []);
  const onSort = useCallback((s: SortKey) => {
    setSort(s);
    setPage(1);
  }, []);

  const categoryLabel =
    CATEGORIES.find((c) => c.id === category)?.label ?? category;

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg-default">
      {/* ── Header: brand · live freshness · catalog size ─────────────── */}
      <header className="sticky top-0 z-30 border-b border-border-default bg-bg-base/85 backdrop-blur-md">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_18rem_at_15%_-8rem,rgba(41,98,255,0.10),transparent)]"
        />
        <div className="relative mx-auto flex w-full max-w-[1400px] items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight">
              etoro
              <span className="ml-2 text-base font-normal text-fg-muted">
                · Screener
              </span>
            </h1>
            <span className="hidden text-xs text-fg-muted/70 sm:inline">
              {categoryLabel}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-border-default bg-bg-base/70 px-3 py-1 text-xs text-fg-muted shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
              <span className="relative inline-flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-green opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-green shadow-[0_0_6px_rgba(38,166,154,0.8)]" />
              </span>
              <span className="font-medium text-fg-default">Live</span>
              <span className="text-fg-muted/60">·</span>
              <span className="tabular-nums">
                {stream.status === "live" ? "streaming" : freshness(status.data?.last_refresh_age_s)}
              </span>
            </span>
            {status.data?.instruments != null && (
              <span className="hidden font-mono text-xs tabular-nums text-fg-muted md:inline">
                {status.data.instruments.toLocaleString()} instruments
              </span>
            )}
          </div>
        </div>
      </header>

      {/* ── Toolbar: tabs + sort, then search + refresh + pagination ──── */}
      {/* top-[65px] MUST equal the header's rendered height (py-4 + text-xl
          line-box) so the two sticky bars sit flush — keep in sync if either
          the header padding or brand type scale changes. */}
      <div className="sticky top-[65px] z-20 border-b border-border-default bg-bg-base/80 backdrop-blur-md">
        <div className="mx-auto w-full max-w-[1400px] px-6">
          <div className="flex flex-wrap items-center gap-3 py-3">
            <CategoryTabs value={category} onChange={onCategory} />

            <label className="ml-auto inline-flex items-center gap-2 text-xs text-fg-muted">
              <span className="hidden sm:inline">Sort by</span>
              <div className="inline-flex items-center gap-0.5 rounded-lg border border-border-default bg-bg-base/60 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
                {SORTS.map((s) => {
                  const active = s.id === sort;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => onSort(s.id)}
                      className={[
                        "rounded-md px-3 py-1 text-sm font-medium tracking-tight whitespace-nowrap",
                        "transition-all duration-200 ease-out",
                        "outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-base",
                        active
                          ? "bg-bg-hover text-fg-default shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
                          : "text-fg-muted hover:text-fg-default hover:bg-bg-hover/60",
                      ].join(" ")}
                    >
                      {s.label}
                    </button>
                  );
                })}
              </div>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-border-default/60 py-3">
            <SearchBox onSearch={onSearch} placeholder={`Search ${categoryLabel}…`} />

            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className={[
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium",
                "border border-border-default bg-bg-surface text-fg-default",
                "transition-all duration-150 ease-out",
                "hover:bg-bg-hover hover:border-accent-blue/40 active:scale-[0.97]",
                "outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-base",
                "disabled:cursor-not-allowed disabled:opacity-50",
              ].join(" ")}
            >
              <span
                aria-hidden="true"
                className={["text-sm leading-none", isFetching ? "animate-spin" : ""].join(" ")}
              >
                ↻
              </span>
              {isFetching ? "Refreshing…" : "Refresh"}
            </button>

            {data && (
              <div className="ml-auto">
                <Pagination
                  page={page}
                  pageSize={PAGE_SIZE}
                  total={data.total}
                  onPage={setPage}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Content ───────────────────────────────────────────────────── */}
      <main className="mx-auto w-full max-w-[1400px] flex-1 overflow-hidden px-6 py-6">
        {isLoading ? (
          <TableSkeleton />
        ) : isError ? (
          <div className="flex h-full items-center justify-center">
            <div className="max-w-sm rounded-xl border border-accent-red/30 bg-accent-red/5 px-6 py-8 text-center shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)]">
              <div aria-hidden="true" className="mb-2 text-2xl text-accent-red/80">
                ⚠
              </div>
              <p className="text-sm font-medium text-fg-default">
                Could not load market data
              </p>
              <p className="mt-1 text-xs text-fg-muted">
                Is the backend running on :8765?
              </p>
              <button
                type="button"
                onClick={() => refetch()}
                className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-border-default bg-bg-surface px-3 py-1.5 text-sm font-medium text-fg-default transition-colors hover:bg-bg-hover"
              >
                <span aria-hidden="true">↻</span> Retry
              </button>
            </div>
          </div>
        ) : (
          data && <ScreenerTable rows={data.items} ticks={stream.ticks} />
        )}
      </main>
    </div>
  );
}
