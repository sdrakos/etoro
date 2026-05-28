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
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted">🔍</span>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-bg-surface border border-border-default rounded-md py-1.5 pl-9 pr-9 text-sm text-fg-default placeholder:text-fg-muted focus:border-accent-blue outline-none"
      />
      {value && (
        <button
          type="button"
          onClick={() => setValue("")}
          aria-label="clear"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-fg-muted hover:text-fg-default"
        >
          ✕
        </button>
      )}
    </div>
  );
}
