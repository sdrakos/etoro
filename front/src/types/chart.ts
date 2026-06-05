export interface Candle {
  time: number;   // epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface ChartResponse {
  instrument_id: number;
  symbol: string | null;
  name: string | null;
  interval: string;
  candles: Candle[];
}
