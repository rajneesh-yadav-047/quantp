/**
 * Shared types for the OptionsTab module.
 */

export interface OptionChainStrike {
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  open_interest: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  iv: number;
  symbol: string;
  token: string;
}

export interface OptionChainData {
  underlying: string;
  symbol: string;
  ltp: number;
  expiry_dates: string[];
  strikes: number[];
  chain: Record<number, { CE?: OptionChainStrike; PE?: OptionChainStrike }>;
  lot_size?: number;
  is_mock?: boolean;
}

export interface StrategyLeg {
  id: string;
  leg_index: number;
  position: "BUY" | "SELL";
  option_type: "CE" | "PE";
  qty: number;
  lot_multiplier: number;
  strike_criteria: string;
  strike_value: number;
  strike_type: string;
  sl_enabled: boolean;
  sl_type: string;
  sl_value: number;
  sl_on_price: string;
  tp_enabled: boolean;
  tp_type: string;
  tp_value: number;
  tp_on_price: string;
  trail_sl_enabled: boolean;
  trail_sl_type: string;
  trail_sl_value: number;
  trail_sl_step: number;
}

export interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  legs_count: number;
  example: string;
}

export interface SavedStrategy {
  id: string;
  name: string;
  description?: string;
  underlying_symbol: string;
  trade_type: string;
  start_time: string;
  end_time: string;
  expiry_type: string;
  strategy_type: string;
  initial_capital: number;
  max_position_size?: number;
  trade_days: { mon: boolean; tue: boolean; wed: boolean; thu: boolean; fri: boolean };
  is_template?: boolean;
  template_name?: string;
  created_at?: string;
  code?: string;
  legs?: StrategyLeg[];
}

export interface PayoffResult {
  spotPrices: number[];
  payoffs: number[];
  maxProfit: number;
  maxLoss: number;
  breakevens: number[];
}

export interface TradeDays {
  mon: boolean;
  tue: boolean;
  wed: boolean;
  thu: boolean;
  fri: boolean;
}
