export function openChart(instrumentId: number): void {
  window.open(`/chart/${instrumentId}`, "_blank", "noopener");
}
