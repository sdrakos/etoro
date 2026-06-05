import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useChartData } from "../hooks/useChartData";
import { usePriceStream } from "../hooks/usePriceStream";
import { Chart, type ChartHandle } from "../components/Chart";
import { ChartToolbar } from "../components/ChartToolbar";
import { toEtoroInterval } from "../lib/intervals";
import { liveCandle } from "../lib/chartLive";

export function ChartView() {
  const { instrumentId } = useParams();
  const id = Number(instrumentId);
  const [tf, setTf] = useState("1d");
  const [active, setActive] = useState<Set<string>>(new Set(["MA", "VOL"]));
  const { data, isLoading, isError } = useChartData(id, toEtoroInterval(tf));
  const stream = usePriceStream();
  const chartRef = useRef<ChartHandle>(null);

  useEffect(() => {
    if (Number.isFinite(id) && id > 0) stream.subscribe([id]);
  }, [id, stream]);

  const candles = useMemo(() => data?.candles ?? [], [data]);

  useEffect(() => {
    const last = candles[candles.length - 1];
    const price = stream.ticks.get(id)?.last;
    if (last && price != null) chartRef.current?.updateLast(liveCandle(last, price));
  }, [stream.ticks, id, candles]);

  const toggle = (name: string) =>
    setActive((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const livePrice = stream.ticks.get(id)?.last;

  return (
    <div className="flex h-screen flex-col bg-bg-base text-fg-default">
      <header className="flex items-baseline gap-3 border-b border-border-default px-4 py-3">
        <span className="font-mono text-lg font-semibold">{data?.symbol ?? `#${id}`}</span>
        {data?.name && <span className="text-sm text-fg-muted">{data.name}</span>}
        {livePrice != null && (
          <span className="ml-auto font-mono tabular-nums text-accent-green">{livePrice.toFixed(2)}</span>
        )}
      </header>
      <ChartToolbar timeframe={tf} onTimeframe={setTf} active={active} onToggle={toggle} />
      <main className="relative flex-1">
        {isLoading && <p className="p-4 text-fg-muted">Loading chart…</p>}
        {isError && (
          <p className="p-4 text-accent-red">Could not load chart. Is the backend running on :8765?</p>
        )}
        {data && candles.length === 0 && (
          <p className="p-4 text-fg-muted">No chart data for this instrument.</p>
        )}
        {data && candles.length > 0 && (
          <Chart ref={chartRef} candles={candles} indicators={[...active]} />
        )}
      </main>
    </div>
  );
}
