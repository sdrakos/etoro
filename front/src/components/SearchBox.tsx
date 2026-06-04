import { useEffect, useState } from "react";

interface Props {
  onSearch: (query: string) => void;
  debounceMs?: number;
  placeholder?: string;
}

export function SearchBox({
  onSearch,
  debounceMs = 200,
  placeholder = "Search ticker or name…",
}: Props) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (debounceMs === 0) {
      onSearch(value);
      return;
    }
    const handle = setTimeout(() => onSearch(value), debounceMs);
    return () => clearTimeout(handle);
  }, [value, debounceMs, onSearch]);

  return (
    <div className="relative flex-1 max-w-md">
      {/* Typographic glyphs (not emoji) so they tint with currentColor and
          render consistently with the rest of the terminal's iconography. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-base leading-none text-fg-muted"
      >
        ⌕
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-border-default bg-bg-surface py-1.5 pl-9 pr-9 text-sm text-fg-default placeholder:text-fg-muted outline-none transition-colors focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/40"
      />
      {value && (
        <button
          type="button"
          onClick={() => setValue("")}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded text-fg-muted outline-none transition-colors hover:text-fg-default focus-visible:ring-2 focus-visible:ring-accent-blue/70"
        >
          ✕
        </button>
      )}
    </div>
  );
}
