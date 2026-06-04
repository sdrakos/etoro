import { useCallback, useEffect, useRef, useState } from "react";

export interface LiveTick {
  bid: number | null;
  ask: number | null;
  last: number | null;
  change_pct: number | null;
  ts: string | null;
}
export type StreamStatus = "connecting" | "live" | "reconnecting" | "down";

export function usePriceStream() {
  const [ticks, setTicks] = useState<Map<number, LiveTick>>(new Map());
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const idsRef = useRef<number[]>([]);
  const ticksRef = useRef<Map<number, LiveTick>>(new Map());
  const backoffRef = useRef(1000);
  const closedRef = useRef(false);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/prices`);
    wsRef.current = ws;
    ws.onopen = () => {
      setStatus("live");
      backoffRef.current = 1000;
      if (idsRef.current.length) ws.send(JSON.stringify({ op: "set", ids: idsRef.current }));
    };
    ws.onmessage = (e) => {
      let t: any;
      try { t = JSON.parse(e.data); } catch { return; }
      if (t && typeof t.instrumentId === "number") {
        const next = new Map(ticksRef.current);
        next.set(t.instrumentId, { bid: t.bid, ask: t.ask, last: t.last, change_pct: t.change_pct, ts: t.ts });
        ticksRef.current = next;
        setTicks(next);
      }
    };
    ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
    ws.onclose = () => {
      if (closedRef.current) return;
      setStatus("reconnecting");
      window.setTimeout(connect, backoffRef.current);
      backoffRef.current = Math.min(backoffRef.current * 2, 30000);
    };
  }, []);

  useEffect(() => {
    closedRef.current = false;
    connect();
    return () => { closedRef.current = true; wsRef.current?.close(); };
  }, [connect]);

  const subscribe = useCallback((ids: number[]) => {
    idsRef.current = ids;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ op: "set", ids }));
  }, []);

  return { ticks, subscribe, status };
}
