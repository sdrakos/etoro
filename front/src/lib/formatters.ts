const DASH = "—";

export function formatMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return DASH;
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toFixed(2)}`;
}

export function formatPercent(n: number | null | undefined): string {
  if (n === null || n === undefined) return DASH;
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function formatVolume(n: number | null | undefined): string {
  if (n === null || n === undefined) return DASH;
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${Math.round(n / 1e6)}M`;
  return n.toLocaleString("en-US");
}

export function formatPE(n: number | null | undefined): string {
  if (n === null || n === undefined) return DASH;
  return n.toFixed(1);
}

export function changeColorClass(n: number | null | undefined): string {
  if (n === null || n === undefined) return "text-fg-muted";
  return n >= 0 ? "text-accent-green" : "text-accent-red";
}
