import { TIMEFRAMES } from "../lib/intervals";

const INDICATORS = ["MA", "EMA", "BOLL", "VOL", "MACD", "RSI", "KDJ"];

interface Props {
  timeframe: string;
  onTimeframe: (id: string) => void;
  active: Set<string>;
  onToggle: (name: string) => void;
  onOpenSettings?: (name: string) => void;
}

const btn =
  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors outline-none " +
  "focus-visible:ring-2 focus-visible:ring-accent-blue/70";

export function ChartToolbar({ timeframe, onTimeframe, active, onToggle, onOpenSettings }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border-default px-4 py-2">
      <div className="flex gap-1">
        {TIMEFRAMES.map((t) => (
          <button key={t.id} type="button" aria-pressed={t.id === timeframe}
            onClick={() => onTimeframe(t.id)}
            className={[btn, t.id === timeframe ? "bg-accent-blue text-white"
              : "text-fg-muted hover:text-fg-default hover:bg-bg-hover"].join(" ")}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-1">
        {INDICATORS.map((n) => (
          <span key={n} className="inline-flex items-center">
            <button type="button" aria-pressed={active.has(n)} onClick={() => onToggle(n)}
              className={[btn, active.has(n) ? "bg-bg-hover text-fg-default"
                : "text-fg-muted hover:text-fg-default hover:bg-bg-hover/60"].join(" ")}>
              {n}
            </button>
            {active.has(n) && onOpenSettings && (
              <button type="button" aria-label={`${n} settings`} onClick={() => onOpenSettings(n)}
                className="ml-0.5 rounded px-1 py-1 text-xs leading-none text-fg-muted hover:text-fg-default outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70">
                ⚙
              </button>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
