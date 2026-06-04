import { changeColorClass } from "../lib/formatters";

interface Props {
  invested: number;
  pnlUsd: number;
  pnlPct: number | null;
}

function signed(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

export function PortfolioSummary({ invested, pnlUsd, pnlPct }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-6 rounded-xl border border-border-default bg-bg-surface/40 px-6 py-4">
      <div>
        <div className="text-xs uppercase tracking-wide text-fg-muted">Invested</div>
        <div className="font-mono text-lg tabular-nums text-fg-default">${invested.toFixed(2)}</div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-fg-muted">Live P&L</div>
        <div className={["font-mono text-lg tabular-nums", changeColorClass(pnlUsd)].join(" ")}>
          {signed(pnlUsd)}
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-fg-muted">Return</div>
        <div className={["font-mono text-lg tabular-nums", changeColorClass(pnlPct ?? 0)].join(" ")}>
          {pnlPct === null ? "—" : `${signed(pnlPct)}%`}
        </div>
      </div>
    </div>
  );
}
