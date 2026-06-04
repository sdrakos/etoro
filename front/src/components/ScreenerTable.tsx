import type { CategoryRow } from "../types/screener";
import { formatPercent, changeColorClass } from "../lib/formatters";

interface Props {
  rows: CategoryRow[];
}

/** Right-aligned price/quote cell — raw toFixed(2) so it stays grep-able and digits line up. */
function num(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}

/** Bucket sentiment into a directional hue so the gauge reads bull/neutral/bear at a glance. */
function sentimentTone(pct: number): { bar: string; text: string } {
  if (pct >= 60) return { bar: "bg-accent-green", text: "text-accent-green" };
  if (pct <= 40) return { bar: "bg-accent-red", text: "text-accent-red" };
  return { bar: "bg-accent-blue", text: "text-fg-default" };
}

const TH =
  "sticky top-0 z-10 bg-bg-base/95 backdrop-blur-sm py-2.5 px-4 " +
  "text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-fg-muted " +
  "border-b border-border-default select-none";

export function ScreenerTable({ rows }: Props) {
  return (
    <div className="h-full overflow-auto rounded-xl border border-border-default bg-bg-base shadow-[0_1px_0_rgba(255,255,255,0.02)_inset,0_8px_24px_-12px_rgba(0,0,0,0.6)]">
      <table className="w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th scope="col" className={`${TH} text-left`}>
              Market
            </th>
            <th scope="col" className={`${TH} text-right`}>
              Change&nbsp;%
            </th>
            <th scope="col" className={`${TH} text-right`}>
              Sell
            </th>
            <th scope="col" className={`${TH} text-right`}>
              Buy
            </th>
            <th scope="col" className={`${TH} text-left`}>
              Sentiment
            </th>
            <th scope="col" className={`${TH} text-right`}>
              Exchange
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const up = (r.change_pct ?? 0) >= 0;
            return (
              <tr
                key={`${r.instrument_id ?? r.ticker}`}
                tabIndex={0}
                className={[
                  "group outline-none transition-colors duration-150",
                  i % 2 === 1 ? "bg-bg-surface/30" : "bg-transparent",
                  "hover:bg-bg-hover focus-visible:bg-bg-hover",
                  "focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent-blue/60",
                ].join(" ")}
              >
                {/* Market: live dot · ticker · name */}
                <td className="py-2.5 px-4 border-b border-border-default/40 whitespace-nowrap">
                  <span className="inline-flex items-center gap-2.5">
                    <span className="relative inline-flex h-2 w-2 shrink-0" title={r.is_open ? "Market open" : "Market closed"}>
                      {r.is_open && (
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-green opacity-60" />
                      )}
                      <span
                        className={[
                          "relative inline-flex h-2 w-2 rounded-full",
                          r.is_open ? "bg-accent-green shadow-[0_0_6px_rgba(38,166,154,0.8)]" : "bg-fg-muted/60",
                        ].join(" ")}
                      />
                    </span>
                    <span className="font-mono font-semibold tracking-tight text-fg-default">
                      {r.ticker}
                    </span>
                    <span className="truncate max-w-[16rem] text-fg-muted group-hover:text-fg-default transition-colors">
                      {r.name}
                    </span>
                  </span>
                </td>

                {/* Change %: signed, color-coded, tabular */}
                <td className="py-2.5 px-4 border-b border-border-default/40 text-right whitespace-nowrap">
                  <span
                    className={[
                      "inline-flex items-center justify-end gap-1 rounded-md px-1.5 py-0.5",
                      "font-mono font-medium tabular-nums",
                      changeColorClass(r.change_pct),
                      r.change_pct === null || r.change_pct === undefined
                        ? ""
                        : up
                          ? "bg-accent-green/10"
                          : "bg-accent-red/10",
                    ].join(" ")}
                  >
                    {(r.change_pct ?? null) !== null && (
                      <span aria-hidden="true" className="text-[0.65rem] leading-none -mr-0.5">
                        {up ? "▲" : "▼"}
                      </span>
                    )}
                    {formatPercent(r.change_pct)}
                  </span>
                </td>

                {/* Sell */}
                <td className="py-2.5 px-4 border-b border-border-default/40 text-right whitespace-nowrap font-mono tabular-nums text-accent-red/90">
                  {num(r.sell)}
                </td>

                {/* Buy */}
                <td className="py-2.5 px-4 border-b border-border-default/40 text-right whitespace-nowrap font-mono tabular-nums text-accent-green/90">
                  {num(r.buy)}
                </td>

                {/* Sentiment gauge */}
                <td className="py-2.5 px-4 border-b border-border-default/40 whitespace-nowrap">
                  {r.sentiment_buy_pct === null || r.sentiment_buy_pct === undefined ? (
                    <span className="text-fg-muted">—</span>
                  ) : (
                    (() => {
                      const pct = Math.max(0, Math.min(100, r.sentiment_buy_pct!));
                      const tone = sentimentTone(pct);
                      return (
                        <span className="inline-flex items-center gap-2.5">
                          <span className="relative inline-block h-1.5 w-20 overflow-hidden rounded-full bg-bg-surface ring-1 ring-inset ring-border-default/60">
                            <span
                              className={`block h-full rounded-full ${tone.bar} transition-[width] duration-500 ease-out`}
                              style={{ width: `${pct}%` }}
                            />
                          </span>
                          <span
                            className={`font-mono text-xs tabular-nums ${tone.text}`}
                            aria-label={`${Math.round(r.sentiment_buy_pct!)}% buy`}
                          >
                            {Math.round(r.sentiment_buy_pct!)}%
                          </span>
                        </span>
                      );
                    })()
                  )}
                </td>

                {/* Exchange chip */}
                <td className="py-2.5 px-4 border-b border-border-default/40 text-right whitespace-nowrap">
                  {r.exchange ? (
                    <span className="inline-flex items-center rounded-md border border-border-default bg-bg-surface/60 px-2 py-0.5 text-xs font-medium text-fg-muted">
                      {r.exchange}
                    </span>
                  ) : (
                    <span className="text-fg-muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}

          {rows.length === 0 && (
            <tr>
              <td
                colSpan={6}
                className="py-12 text-center text-fg-muted border-b border-border-default/40"
              >
                <span className="inline-flex flex-col items-center gap-1">
                  <span className="text-2xl opacity-40" aria-hidden="true">∅</span>
                  <span className="text-sm">No instruments.</span>
                </span>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
