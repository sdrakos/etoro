import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { init, dispose } from "klinecharts";
import type { Candle } from "../types/chart";

export interface ChartHandle {
  updateLast: (c: Candle) => void;
}

interface Props {
  candles: Candle[];
  indicators: string[];
}

const MAIN_OVERLAYS = ["MA", "EMA", "BOLL"];

function toKline(c: Candle) {
  return { timestamp: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
           volume: c.volume ?? undefined };
}

export const Chart = forwardRef<ChartHandle, Props>(function Chart({ candles, indicators }, ref) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof init> | null>(null);
  const panes = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    chartRef.current = init(elRef.current!);
    return () => {
      if (elRef.current) dispose(elRef.current);
      chartRef.current = null;
      panes.current.clear();
    };
  }, []);

  useEffect(() => {
    chartRef.current?.applyNewData(candles.map(toKline));
  }, [candles]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const active = new Set(indicators);
    for (const [name, paneId] of [...panes.current]) {
      if (!active.has(name)) {
        chart.removeIndicator(paneId, name);
        panes.current.delete(name);
      }
    }
    for (const name of active) {
      if (panes.current.has(name)) continue;
      if (MAIN_OVERLAYS.includes(name)) {
        chart.createIndicator(name, false, { id: "candle_pane" });
        panes.current.set(name, "candle_pane");
      } else {
        const paneId = chart.createIndicator(name);
        if (paneId) panes.current.set(name, paneId);
      }
    }
  }, [indicators]);

  useImperativeHandle(ref, () => ({
    updateLast: (c) => chartRef.current?.updateData(toKline(c)),
  }), []);

  return <div ref={elRef} className="h-full w-full" />;
});
