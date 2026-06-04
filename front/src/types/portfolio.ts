export interface Position {
  position_id: number;
  instrument_id: number;
  symbol: string | null;
  name: string | null;
  is_buy: boolean;
  units: number;
  open_rate: number;
  amount: number;
  leverage: number;
  current_rate: number | null;
}

export interface PortfolioResponse {
  positions: Position[];
  account: string;
}
