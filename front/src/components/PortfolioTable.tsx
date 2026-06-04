import type { Position } from "../types/portfolio";
import type { LiveTick } from "../hooks/usePriceStream";
import { positionPnl } from "../lib/pnl";
import { changeColorClass } from "../lib/formatters";

interface Props {
  rows: Position[];
  ticks: Map<number, LiveTick>;
  onClose: (p: Position) => void;
  closingId: number | null;
}

function num(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}
function signed(v: number | null): string {
  return v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

export function PortfolioTable({ rows, ticks, onClose, closingId }: Props) {
  return (
    <div className="overflow-auto rounded-xl border border-border-default bg-bg-base">
      <table className="w-full text-sm">
        <thead className="text-left text-fg-muted border-b border-border-default">
          <tr>
            <th className="py-2.5 px-4">Market</th>
            <th className="py-2.5 px-4">Direction</th>
            <th className="py-2.5 px-4 text-right">Units</th>
            <th className="py-2.5 px-4 text-right">Open</th>
            <th className="py-2.5 px-4 text-right">Current</th>
            <th className="py-2.5 px-4 text-right">P&L $</th>
            <th className="py-2.5 px-4 text-right">P&L %</th>
            <th className="py-2.5 px-4"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const { price, pnlUsd, pnlPct } = positionPnl(p, ticks.get(p.instrument_id)?.last);
            return (
              <tr key={p.position_id} className="border-b border-border-default/50 hover:bg-bg-hover">
                <td className="py-2.5 px-4">
                  <span className="font-mono font-semibold text-fg-default">{p.symbol ?? `#${p.instrument_id}`}</span>
                  {p.name && <span className="ml-2 text-fg-muted">{p.name}</span>}
                </td>
                <td className="py-2.5 px-4">{p.is_buy ? "Buy" : "Sell"}</td>
                <td className="py-2.5 px-4 text-right font-mono tabular-nums">{p.units.toFixed(4)}</td>
                <td className="py-2.5 px-4 text-right font-mono tabular-nums">{p.open_rate.toFixed(2)}</td>
                <td className="py-2.5 px-4 text-right font-mono tabular-nums">{num(price)}</td>
                <td className={["py-2.5 px-4 text-right font-mono tabular-nums", changeColorClass(pnlUsd ?? 0)].join(" ")}>{signed(pnlUsd)}</td>
                <td className={["py-2.5 px-4 text-right font-mono tabular-nums", changeColorClass(pnlPct ?? 0)].join(" ")}>{pnlPct === null ? "—" : `${signed(pnlPct)}%`}</td>
                <td className="py-2.5 px-4 text-right">
                  <button
                    type="button"
                    onClick={() => onClose(p)}
                    disabled={closingId === p.position_id}
                    className="rounded-md border border-border-default bg-bg-surface px-3 py-1 text-xs font-medium text-fg-default hover:bg-bg-hover disabled:opacity-50"
                  >
                    {closingId === p.position_id ? "Closing…" : "Close"}
                  </button>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr><td colSpan={8} className="py-8 text-center text-fg-muted">No open positions.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
