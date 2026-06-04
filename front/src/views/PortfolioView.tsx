import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePortfolio } from "../hooks/usePortfolio";
import { usePriceStream } from "../hooks/usePriceStream";
import { closePosition } from "../api/portfolio";
import { positionPnl, aggregatePnl } from "../lib/pnl";
import { PortfolioSummary } from "../components/PortfolioSummary";
import { PortfolioTable } from "../components/PortfolioTable";
import type { Position } from "../types/portfolio";

export function PortfolioView() {
  const { data, isLoading, isError } = usePortfolio();
  const stream = usePriceStream();
  const qc = useQueryClient();
  const [closingId, setClosingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const positions = data?.positions ?? [];

  useEffect(() => {
    const ids = positions.map((p) => p.instrument_id);
    if (ids.length) stream.subscribe(ids);
  }, [data, stream]);

  const priced = positions.map((p) => ({
    p, price: positionPnl(p, stream.ticks.get(p.instrument_id)?.last).price,
  }));
  const agg = aggregatePnl(priced);

  async function onClose(p: Position) {
    if (!window.confirm(`Close ${p.symbol ?? p.instrument_id} (${p.is_buy ? "Buy" : "Sell"} ${p.units})?`)) return;
    setClosingId(p.position_id);
    setError(null);
    try {
      await closePosition(p.position_id, { InstrumentID: p.instrument_id });
      await qc.invalidateQueries({ queryKey: ["portfolio"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Close failed");
    } finally {
      setClosingId(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6 space-y-4">
      {isLoading && <p className="text-fg-muted">Loading portfolio…</p>}
      {isError && (
        <div className="text-accent-red">Could not load portfolio. Is the backend running on :8765?</div>
      )}
      {error && <div className="text-accent-red text-sm">{error}</div>}
      {data && (
        <>
          <PortfolioSummary invested={agg.invested} pnlUsd={agg.pnlUsd} pnlPct={agg.pnlPct} />
          <PortfolioTable rows={positions} ticks={stream.ticks} onClose={onClose} closingId={closingId} />
        </>
      )}
    </main>
  );
}
