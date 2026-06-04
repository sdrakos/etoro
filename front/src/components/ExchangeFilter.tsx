import type { ExchangeOption } from "../types/screener";

interface Props {
  value: string | null;
  options: ExchangeOption[];
  onChange: (exchange: string | null) => void;
}

const ALL = "__all__";

export function ExchangeFilter({ value, options, onChange }: Props) {
  return (
    <label className="inline-flex items-center gap-2 text-xs text-fg-muted">
      <span className="hidden sm:inline">Exchange</span>
      <select
        value={value ?? ALL}
        disabled={options.length <= 1}
        onChange={(e) => onChange(e.target.value === ALL ? null : e.target.value)}
        className="rounded-md border border-border-default bg-bg-surface px-2 py-1.5 text-sm text-fg-default outline-none transition-colors focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/40 disabled:opacity-50"
      >
        <option value={ALL}>All exchanges</option>
        {options.map((o) => (
          <option key={o.exchange} value={o.exchange}>
            {o.exchange} ({o.count})
          </option>
        ))}
      </select>
    </label>
  );
}
