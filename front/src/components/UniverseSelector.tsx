import { UNIVERSES, type Universe } from "../types/screener";

interface Props {
  value: Universe;
  onChange: (universe: Universe) => void;
  count?: number;
}

export function UniverseSelector({ value, onChange, count }: Props) {
  return (
    <div className="flex items-center gap-4">
      <div className="inline-flex rounded-md border border-border-default overflow-hidden">
        {UNIVERSES.map(({ id, label }) => {
          const active = id === value;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              aria-pressed={active}
              className={[
                "px-4 py-1.5 text-sm font-medium transition-colors",
                active
                  ? "bg-accent-blue text-white"
                  : "bg-bg-surface text-fg-default hover:bg-bg-hover",
              ].join(" ")}
            >
              {label}
            </button>
          );
        })}
      </div>
      {count !== undefined && (
        <span className="text-sm text-fg-muted">{count} stocks</span>
      )}
    </div>
  );
}
