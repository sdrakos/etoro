import { useEffect, useState } from "react";
import { paramLabels, type IndicatorConfig } from "../lib/indicators";

interface Props {
  name: string;
  config: IndicatorConfig;
  onApply: (c: IndicatorConfig) => void;
  onReset: () => void;
  onClose: () => void;
}

const tabBtn =
  "rounded-t-md px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70";

export function IndicatorSettingsModal({ name, config, onApply, onReset, onClose }: Props) {
  const [tab, setTab] = useState<"inputs" | "style">("inputs");
  const labels = paramLabels(name);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const setParam = (i: number, v: number) =>
    onApply({ ...config, calcParams: config.calcParams.map((p, idx) => (idx === i ? v : p)) });
  const setColor = (i: number, v: string) =>
    onApply({ ...config, colors: config.colors.map((c, idx) => (idx === i ? v : c)) });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-label={`${name} settings`}
      onClick={onClose}
    >
      <div
        className="w-80 rounded-xl border border-border-default bg-bg-base shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
          <h2 className="font-semibold">{name} settings</h2>
          <button type="button" aria-label="Close" onClick={onClose}
            className="text-fg-muted hover:text-fg-default">✕</button>
        </div>

        <div className="flex gap-1 border-b border-border-default px-4 pt-2">
          {(["inputs", "style"] as const).map((t) => (
            <button key={t} type="button" aria-pressed={tab === t} onClick={() => setTab(t)}
              className={[tabBtn, tab === t ? "bg-bg-hover text-fg-default"
                : "text-fg-muted hover:text-fg-default"].join(" ")}>
              {t === "inputs" ? "Inputs" : "Style"}
            </button>
          ))}
        </div>

        <div className="space-y-3 px-4 py-4">
          {tab === "inputs"
            ? config.calcParams.map((p, i) => (
                <label key={i} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-fg-muted">{labels[i] ?? `Param ${i + 1}`}</span>
                  <input
                    type="number"
                    min={1}
                    value={p}
                    onChange={(e) => setParam(i, Number(e.target.value))}
                    className="w-24 rounded border border-border-default bg-bg-surface px-2 py-1 text-right tabular-nums"
                  />
                </label>
              ))
            : config.colors.map((c, i) => (
                <label key={i} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-fg-muted">Line {i + 1}</span>
                  <input
                    type="color"
                    aria-label={`Line ${i + 1} color`}
                    value={c}
                    onChange={(e) => setColor(i, e.target.value)}
                    className="h-7 w-12 rounded border border-border-default bg-transparent"
                  />
                </label>
              ))}
        </div>

        <div className="flex items-center justify-between border-t border-border-default px-4 py-3">
          <button type="button" onClick={onReset}
            className="text-sm text-fg-muted hover:text-fg-default">Reset to defaults</button>
          <button type="button" onClick={onClose}
            className="rounded-md bg-accent-blue px-3 py-1.5 text-sm font-medium text-white">Done</button>
        </div>
      </div>
    </div>
  );
}
