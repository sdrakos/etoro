export type AppView = "screener" | "portfolio";

const VIEWS: { id: AppView; label: string }[] = [
  { id: "screener", label: "Screener" },
  { id: "portfolio", label: "Portfolio" },
];

interface Props {
  value: AppView;
  onChange: (v: AppView) => void;
}

export function AppNav({ value, onChange }: Props) {
  return (
    <nav className="mx-auto flex w-full max-w-[1400px] items-center gap-1 px-6 py-2">
      {VIEWS.map(({ id, label }) => {
        const active = id === value;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(id)}
            className={[
              "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              "outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70",
              active ? "bg-bg-hover text-fg-default" : "text-fg-muted hover:text-fg-default hover:bg-bg-hover/60",
            ].join(" ")}
          >
            {label}
          </button>
        );
      })}
    </nav>
  );
}
