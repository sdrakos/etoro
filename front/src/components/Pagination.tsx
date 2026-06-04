interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}

const arrowBtn = [
  "inline-flex items-center gap-1 rounded-md px-2.5 py-1.5",
  "text-sm font-medium text-fg-default",
  "border border-border-default bg-bg-surface",
  "transition-all duration-150 ease-out",
  "hover:bg-bg-hover hover:border-accent-blue/40 hover:text-white",
  "active:scale-[0.97]",
  "outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-base",
  "disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-bg-surface disabled:hover:border-border-default disabled:hover:text-fg-default disabled:active:scale-100",
].join(" ");

export function Pagination({ page, pageSize, total, onPage }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center gap-3 text-sm text-fg-muted select-none"
    >
      <button
        type="button"
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
        className={arrowBtn}
      >
        <span aria-hidden="true" className="text-base leading-none -mt-px">
          ‹
        </span>
        Prev
      </button>

      <div className="flex items-center gap-1.5 rounded-md border border-border-default bg-bg-base/70 px-3 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
        <span className="font-mono text-xs tabular-nums text-fg-default">
          {page}
        </span>
        <span className="text-fg-muted/60">/</span>
        <span className="font-mono text-xs tabular-nums text-fg-muted">
          {pages}
        </span>
        <span
          aria-hidden="true"
          className="mx-1 h-3 w-px bg-border-default"
        />
        <span className="font-mono text-xs tabular-nums text-fg-muted">
          {total.toLocaleString()}
        </span>
        <span className="text-fg-muted/70">items</span>
      </div>

      <button
        type="button"
        onClick={() => onPage(page + 1)}
        disabled={page >= pages}
        aria-label="Next page"
        className={arrowBtn}
      >
        Next
        <span aria-hidden="true" className="text-base leading-none -mt-px">
          ›
        </span>
      </button>
    </nav>
  );
}
