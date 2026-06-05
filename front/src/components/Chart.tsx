import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { init, dispose, type IndicatorCreate } from "klinecharts";
import type { Candle } from "../types/chart";
import { klineStyles, type IndicatorConfig } from "../lib/indicators";

export interface ChartHandle {
  updateLast: (c: Candle) => void;
}

interface Props {
  candles: Candle[];
  indicators: IndicatorConfig[];
}

const MAIN_OVERLAYS = ["MA", "EMA", "BOLL"];

function toKline(c: Candle) {
  return { timestamp: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
           volume: c.volume ?? undefined };
}

export const Chart = forwardRef<ChartHandle, Props>(function Chart({ candles, indicators }, ref) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof init> | null>(null);
  const tracked = useRef<Map<string, { paneId: string; sig: string }>>(new Map());

  useEffect(() => {
    chartRef.current = init(elRef.current!);
    return () => {
      if (elRef.current) dispose(elRef.current);
      chartRef.current = null;
      tracked.current.clear();
    };
  }, []);

  useEffect(() => {
    chartRef.current?.applyNewData(candles.map(toKline));
  }, [candles]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const byName = new Map(indicators.map((i) => [i.name, i]));

    for (const [name, info] of [...tracked.current]) {
      if (!byName.has(name)) {
        chart.removeIndicator(info.paneId, name);
        tracked.current.delete(name);
      }
    }

    for (const cfg of indicators) {
      const value = { name: cfg.name, calcParams: cfg.calcParams, styles: klineStyles(cfg.colors) } as IndicatorCreate;
      const sig = JSON.stringify({ p: cfg.calcParams, c: cfg.colors });
      const existing = tracked.current.get(cfg.name);
      if (!existing) {
        const paneId = MAIN_OVERLAYS.includes(cfg.name)
          ? chart.createIndicator(value, false, { id: "candle_pane" })
          : chart.createIndicator(value);
        if (paneId) tracked.current.set(cfg.name, { paneId, sig });
      } else if (existing.sig !== sig) {
        chart.overrideIndicator(value, existing.paneId);
        tracked.current.set(cfg.name, { paneId: existing.paneId, sig });
      }
    }
  }, [indicators]);

  useImperativeHandle(ref, () => ({
    updateLast: (c) => chartRef.current?.updateData(toKline(c)),
  }), []);

  return <div ref={elRef} className="h-full w-full" />;
});
