export interface IndicatorConfig {
  name: string;
  calcParams: number[];
  colors: string[];   // one color per drawn line (may differ from calcParams.length)
}

interface IndicatorDef {
  calcParams: number[];
  labels: string[];
  colors: string[];
}

// Distinct, theme-friendly line palette.
const PALETTE = ["#EFB90B", "#935EBD", "#2962FF", "#E5436F"];

const DEFS: Record<string, IndicatorDef> = {
  MA: { calcParams: [5, 10, 30, 60], labels: ["MA1", "MA2", "MA3", "MA4"], colors: PALETTE.slice(0, 4) },
  EMA: { calcParams: [6, 12, 20], labels: ["EMA1", "EMA2", "EMA3"], colors: PALETTE.slice(0, 3) },
  BOLL: { calcParams: [20, 2], labels: ["Period", "StdDev"], colors: PALETTE.slice(0, 3) },
  VOL: { calcParams: [5, 10, 20], labels: ["MA1", "MA2", "MA3"], colors: PALETTE.slice(0, 3) },
  MACD: { calcParams: [12, 26, 9], labels: ["Short", "Long", "Signal"], colors: PALETTE.slice(0, 2) },
  RSI: { calcParams: [6, 12, 24], labels: ["RSI1", "RSI2", "RSI3"], colors: PALETTE.slice(0, 3) },
  KDJ: { calcParams: [9, 3, 3], labels: ["K", "D", "J"], colors: PALETTE.slice(0, 3) },
};

export const INDICATORS = ["MA", "EMA", "BOLL", "VOL", "MACD", "RSI", "KDJ"] as const;

export function defaultConfig(name: string): IndicatorConfig {
  const d = DEFS[name] ?? { calcParams: [], labels: [], colors: [] };
  return { name, calcParams: [...d.calcParams], colors: [...d.colors] };
}

export function paramLabels(name: string): string[] {
  return DEFS[name]?.labels ?? [];
}

export function klineStyles(colors: string[]): { lines: { color: string }[] } {
  return { lines: colors.map((color) => ({ color })) };
}
