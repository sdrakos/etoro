import { useState } from "react";
import { useUniverse } from "./hooks/useUniverse";
import { useScreenerData } from "./hooks/useScreenerData";
import { UniverseSelector } from "./components/UniverseSelector";
import { SearchBox } from "./components/SearchBox";
import { ScreenerTable } from "./components/ScreenerTable";

export default function App() {
  const [universe, setUniverse] = useUniverse();
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, refetch, isFetching } = useScreenerData(universe);

  return (
    <div className="min-h-screen flex flex-col bg-bg-base text-fg-default">
      <header className="px-6 py-4 border-b border-border-default flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">
          etoro <span className="text-fg-muted text-base font-normal">· Screener</span>
        </h1>
        <span className="text-xs text-fg-muted">Phase 2A</span>
      </header>

      <div className="px-6 py-3 border-b border-border-default flex items-center gap-4">
        <UniverseSelector
          value={universe}
          onChange={setUniverse}
          count={data?.length}
        />
      </div>

      <div className="px-6 py-3 border-b border-border-default flex items-center gap-3">
        <SearchBox onSearch={setSearch} />
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="px-3 py-1.5 text-sm bg-bg-surface border border-border-default rounded-md hover:bg-bg-hover disabled:opacity-50"
        >
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <main className="flex-1 p-6 overflow-hidden">
        {isLoading && <p className="text-fg-muted">Loading screener…</p>}
        {isError && (
          <div className="text-accent-red">
            Could not load data. Is the backend running on :8765?
          </div>
        )}
        {data && <ScreenerTable rows={data} filter={search} />}
      </main>
    </div>
  );
}
