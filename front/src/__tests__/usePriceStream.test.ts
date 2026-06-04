import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePriceStream } from "../hooks/usePriceStream";

// Minimal mock WebSocket capturing the latest instance.
class MockWS {
  static last: MockWS | null = null;
  static OPEN = 1;
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { MockWS.last = this; }
  send(d: string) { this.sent.push(d); }
  close() { this.readyState = 3; this.onclose?.(); }
  _open() { this.readyState = 1; this.onopen?.(); }
  _msg(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}

describe("usePriceStream", () => {
  beforeEach(() => {
    MockWS.last = null;
    vi.stubGlobal("WebSocket", MockWS as unknown as typeof WebSocket);
  });

  it("subscribes after open and records ticks", async () => {
    const { result } = renderHook(() => usePriceStream());
    act(() => { result.current.subscribe([100000]); });
    act(() => { MockWS.last!._open(); });            // resends ids on open
    expect(JSON.parse(MockWS.last!.sent.at(-1)!)).toEqual({ op: "set", ids: [100000] });

    act(() => { MockWS.last!._msg({ instrumentId: 100000, bid: 1, ask: 2, last: 1.5, change_pct: 3, ts: "T" }); });
    await waitFor(() => expect(result.current.ticks.get(100000)?.bid).toBe(1));
    expect(result.current.status).toBe("live");
  });
});
