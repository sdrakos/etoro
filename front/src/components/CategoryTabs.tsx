import { CATEGORIES, type Category } from "../types/screener";

interface Props {
  value: Category;
  onChange: (c: Category) => void;
}

/** Decorative glyphs per category — aria-hidden so the accessible name stays the plain label. */
const GLYPHS: Record<Category, string> = {
  stocks: "▤",
  crypto: "₿",
  etf: "◳",
  indices: "∿",
  commodities: "⛏",
  currencies: "$",
};

export function CategoryTabs({ value, onChange }: Props) {
  return (
    <div
      aria-label="Asset category"
      className="inline-flex items-center gap-0.5 rounded-lg border border-border-default bg-bg-base/60 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] backdrop-blur-sm"
    >
      {CATEGORIES.map(({ id, label }) => {
        const active = id === value;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(id)}
            className={[
              "group relative inline-flex items-center gap-1.5 rounded-md px-3.5 py-1.5",
              "text-sm font-medium tracking-tight whitespace-nowrap",
              "transition-all duration-200 ease-out",
              "outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-base",
              active
                ? "bg-accent-blue text-white shadow-[0_1px_2px_rgba(0,0,0,0.4),0_0_0_1px_rgba(41,98,255,0.35),0_4px_14px_-4px_rgba(41,98,255,0.55)]"
                : "text-fg-muted hover:text-fg-default hover:bg-bg-hover",
            ].join(" ")}
          >
            <span
              aria-hidden="true"
              className={[
                "text-[0.7rem] leading-none transition-opacity duration-200",
                active ? "opacity-90" : "opacity-50 group-hover:opacity-80",
              ].join(" ")}
            >
              {GLYPHS[id]}
            </span>
            {label}
          </button>
        );
      })}
    </div>
  );
}
