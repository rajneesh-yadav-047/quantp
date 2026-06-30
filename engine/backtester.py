"""
Event-driven backtesting engine with Prosperity runtime integration and options support.

Redesigned architecture:
- BacktestOrchestrator: main event loop, timestamp alignment, state building
- PortfolioManager: position tracking, P&L, margin, liquidation (engine.portfolio)
- OrderManager: order lifecycle, matching, position sizing (engine.order_manager)
- ReplayLogger: JSONL replay events (engine.replay_logger)
- RuntimeFactory: strategy runtime selection (engine.runtime.runtimes)

The orchestrator delegates all domain logic to specialized components,
keeping the main loop clean and focused on event sequencing.
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from engine.datamodels import Candle, MarketState
from engine.execution import ExecutionSimulator, calculate_options_charges
from engine.portfolio import PortfolioManager
from engine.order_manager import OrderManager
from engine.replay_logger import ReplayLogger
from engine.runtime.runtimes import RuntimeFactory, LegacyRuntime
from engine.runtime.adapters import (
    CandleToOrderBookAdapter,
    PortfolioStateBuilder,
)
from engine.runtime.datamodels import (
    Order as ROrder, Trade as RTrade, TradingState
)
from engine.options_catalog import resolve_token
from engine.options_data import OptionsDataManager, bsm_price, generate_bsm_candle


class _OptionsTradeWrapper:
    """Lightweight wrapper so options trade dicts behave like Trade objects where needed."""
    def __init__(self, data: dict):
        self.__dict__.update(data)


class BacktestEngine:
    """
    Event-driven backtester with Prosperity-compatible strategy runtime.

    Responsibilities (orchestrator only):
    1. Align timestamps across symbols
    2. Per-tick: build state, execute strategy, delegate execution
    3. Persist trader_data across ticks
    4. Generate replay events
    """

    def __init__(
        self,
        df_dict: Dict[str, pd.DataFrame],
        strategy_code: str,
        initial_capital: float = 100000.0,
        slippage_pct: float = 0.0005,
        default_trade_type: str = "INTRADAY",
        max_position_size: Optional[int] = None,
        log_dir: str = "./logs",
        parameters: Optional[Dict[str, Any]] = None,
        runtime_type: Optional[str] = None,
        spread_pct: float = 0.01,
        options_slippage_pct: float = 0.01,
    ):
        self.df_dict = df_dict
        self.strategy_code = strategy_code
        self.initial_capital = initial_capital
        self.log_dir = log_dir
        self.runtime_type = runtime_type
        self.default_trade_type = default_trade_type
        self.options_slippage_pct = options_slippage_pct

        # Backtest date range for on-the-fly options data download
        self._backtest_start_date = None
        self._backtest_end_date = None

        # Components
        self.execution_sim = ExecutionSimulator(
            slippage_pct=slippage_pct,
            default_trade_type=default_trade_type
        )
        self.portfolio_mgr = PortfolioManager(
            initial_capital=initial_capital,
            default_trade_type=default_trade_type,
            execution_sim=self.execution_sim,
        )
        self.order_mgr = OrderManager(
            execution_sim=self.execution_sim,
            max_position_size=max_position_size,
        )
        self.runtime = RuntimeFactory.create_runtime(
            strategy_code=strategy_code,
            runtime_type=runtime_type,
            parameters=parameters
        )
        self.order_book_adapter = CandleToOrderBookAdapter(
            spread_pct=spread_pct,
            depth_size=100
        )
        self.options_data_mgr = OptionsDataManager()

        # Pricing mode tracking: REAL_DATA or BSM_APPROXIMATION
        self.pricing_mode: str = "BSM_APPROXIMATION"
        self._used_real_data_contracts: set = set()
        self._used_bsm_contracts: set = set()

        os.makedirs(self.log_dir, exist_ok=True)

        # Historical candles for legacy on_bar strategies
        self.historical_candles: Dict[str, List[Candle]] = {sym: [] for sym in df_dict.keys()}

        # Options position tracking keyed by (symbol, expiry, strike, option_type)
        self.options_positions: Dict[str, Dict[str, Any]] = {}

        self._normalize_time_columns()
        self.all_timestamps = self._align_timestamps()

        # Extract backtest date range from timestamps for on-the-fly download
        if self.all_timestamps:
            self._backtest_start_date = str(self.all_timestamps[0])[:10]
            self._backtest_end_date = str(self.all_timestamps[-1])[:10]

    def _normalize_time_columns(self):
        """Parse and reformat every dataframe's 'time' column to '%Y-%m-%d %H:%M:%S' strings."""
        for symbol, df in self.df_dict.items():
            if 'time' not in df.columns:
                continue
            try:
                parsed = pd.to_datetime(df['time'], errors='coerce')
                if parsed.isna().any():
                    bad_count = parsed.isna().sum()
                    print(f"WARN: Dropping {bad_count} rows with unparseable time in {symbol}")
                    df.drop(index=df.index[parsed.isna()], inplace=True)
                    parsed = pd.to_datetime(df['time'], errors='coerce')
                df['time'] = parsed.dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"WARN: Could not normalize time column for {symbol}: {e}")

    def _align_timestamps(self) -> List[str]:
        """Collect and sort all unique timestamps across symbols."""
        timestamps = set()
        for symbol, df in self.df_dict.items():
            if 'time' in df.columns:
                timestamps.update(df['time'].astype(str).tolist())
            elif isinstance(df.index, pd.DatetimeIndex):
                timestamps.update(df.index.strftime('%Y-%m-%d %H:%M:%S').tolist())
        return sorted(list(timestamps))

    def _get_underlying_spot(self, symbol: str, ts: str) -> Optional[float]:
        """Fetch the underlying spot price from the equity dataset for a given symbol."""
        df = self.df_dict.get(symbol)
        if df is None:
            # Try common underlying name mappings
            mappings = {
                "NIFTY": "NSE:NIFTY 50-EQ",
                "NSE:NIFTY 50-EQ": "NSE:NIFTY 50",
                "NSE:NIFTY 50": "NSE:NIFTY 50-EQ",
                "BANKNIFTY": "NSE:NIFTY BANK-EQ",
                "FINNIFTY": "NSE:NIFTY FIN SERVICE-EQ",
                "NIFTY 50": "NSE:NIFTY 50-EQ",
            }
            mapped = mappings.get(symbol.upper())
            df = self.df_dict.get(mapped) if mapped else None
            if df is None:
                # Try any key that contains the symbol name
                for key in self.df_dict.keys():
                    if symbol.upper() in key.upper() or (mapped and mapped.upper() in key.upper()):
                        df = self.df_dict.get(key)
                        break
            if df is None and not hasattr(self, '_debug_spot_keys_printed'):
                print(f"DEBUG _get_underlying_spot: symbol={symbol} mapped={mapped} df_keys={list(self.df_dict.keys())}")
                self._debug_spot_keys_printed = True
            if df is None:
                return None
        mask = df['time'].astype(str) == ts
        rows = df[mask]
        if not rows.empty:
            return float(rows.iloc[0]['close'])
        # Diagnostic: print timestamp mismatch once
        if not hasattr(self, '_debug_spot_ts_printed'):
            sample_times = df['time'].astype(str).head(5).tolist()
            print(f"DEBUG _get_underlying_spot: timestamp mismatch. ts={ts}, sample_times={sample_times}, df_len={len(df)}")
            self._debug_spot_ts_printed = True
        return None

    def _process_options_orders(self, submitted_orders: List[Any], ts: str) -> List[Any]:
        """
        Handle strategy orders with instrument_type == 'OPTION'.
        Resolves token, fetches OHLC, applies slippage, calculates charges,
        and tracks positions in options_positions.
        """
        trades: List[Any] = []
        for order_req in submitted_orders:
            d = self._normalize_options_order(order_req)
            if not d:
                continue

            symbol = d["symbol"]
            expiry = d["expiry"]
            strike = float(d["strike"])
            option_type = d["option_type"]
            action = d["action"].upper()  # BUY or SELL
            quantity_lots = int(d["quantity_lots"])

            # Resolve token and lot size
            contract = resolve_token(symbol, expiry, strike, option_type, fallback_to_snapshots=True)
            if not contract:
                # Fallback for expired contracts: use lot_size from order if provided, else 75
                lotsize = int(d.get("lot_size", 75))
                tradingsymbol = f"NIFTY{expiry.replace('-', '')}{int(strike)}{option_type}"
                print(f"INFO: Using synthetic contract for expired option {tradingsymbol}, lotsize={lotsize}")
            else:
                lotsize = int(d.get("lot_size", contract.get("lotsize", 75)))
                tradingsymbol = contract.get("tradingsymbol", f"{symbol}-{expiry}-{strike}-{option_type}")

            # Fetch 1-minute candle for this timestamp
            df_opts = self.options_data_mgr.get_ohlc(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                from_dt=ts[:10],
                to_dt=ts[:10],
                interval="ONE_MINUTE",
            )
            # On-the-fly download only if we have a real token
            if (df_opts is None or df_opts.empty) and contract and self._backtest_start_date and self._backtest_end_date:
                token = contract.get("token")
                if token:
                    print(f"INFO: Options data missing for {tradingsymbol}. Attempting on-the-fly download...")
                    try:
                        self.options_data_mgr.fetch_and_store(
                            token=token,
                            tradingsymbol=tradingsymbol,
                            expiry=expiry,
                            strike=strike,
                            option_type=option_type,
                            lotsize=lotsize,
                            from_dt=f"{self._backtest_start_date} 09:15",
                            to_dt=f"{self._backtest_end_date} 15:30",
                        )
                    except Exception as e:
                        print(f"WARN: On-the-fly download failed for {tradingsymbol}: {e}")
                    # Retry read
                    df_opts = self.options_data_mgr.get_ohlc(
                        symbol=symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=option_type,
                        from_dt=ts[:10],
                        to_dt=ts[:10],
                        interval="ONE_MINUTE",
                    )

            if df_opts is None or df_opts.empty:
                # BSM fallback: generate synthetic candle from theoretical price
                underlying_spot = self._get_underlying_spot(symbol, ts)
                if underlying_spot is None:
                    print(f"WARN: No options data for {tradingsymbol} on {ts} and no underlying spot for BSM fallback.")
                    continue

                # Time to expiry in years (expiry at 15:30)
                expiry_dt = datetime.strptime(expiry, "%Y-%m-%d").replace(hour=15, minute=30, second=0)
                current_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                T = max((expiry_dt - current_dt).total_seconds() / (365.25 * 24 * 3600), 0.0)

                synth_price = bsm_price(underlying_spot, strike, T, option_type, iv=0.15, r=0.065)
                df_opts = generate_bsm_candle(
                    timestamp=ts,
                    S=underlying_spot,
                    K=strike,
                    T=T,
                    option_type=option_type,
                    iv=0.15,
                    r=0.065,
                    lot_size=lotsize,
                )
                self._used_bsm_contracts.add((symbol, expiry, strike, option_type))
                print(f"INFO: BSM fallback for {tradingsymbol} on {ts}: price={synth_price:.2f}")
            else:
                self._used_real_data_contracts.add((symbol, expiry, strike, option_type))

            # Find nearest candle to ts
            df_opts["datetime"] = pd.to_datetime(df_opts["datetime"])
            target = pd.to_datetime(ts)
            time_diffs = (df_opts["datetime"] - target).abs()
            nearest_idx = time_diffs.idxmin()
            candle = df_opts.loc[nearest_idx]

            close_p = float(candle["close"])
            # Slippage as percentage of premium
            sign = 1 if action == "BUY" else -1
            fill_price = close_p * (1 + self.options_slippage_pct * sign)
            qty = quantity_lots * lotsize

            # Calculate charges
            charges = calculate_options_charges(
                transaction_type=action,
                premium=fill_price,
                strike=strike,
                lot_size=lotsize,
                quantity_lots=quantity_lots,
                is_expiry_day=False,
                is_itm=False,
            )

            pos_key = f"{symbol}|{expiry}|{strike}|{option_type}"
            if action == "BUY":
                # Reduce cash by premium + charges
                self.portfolio_mgr.portfolio.cash -= (fill_price * qty)
                self.portfolio_mgr.portfolio.cash -= charges["total_charges"]
                self.portfolio_mgr.portfolio.total_fees += charges["total_charges"]
                # Update position
                if pos_key not in self.options_positions:
                    self.options_positions[pos_key] = {
                        "symbol": symbol,
                        "expiry": expiry,
                        "strike": strike,
                        "option_type": option_type,
                        "lotsize": lotsize,
                        "long_qty": 0,
                        "short_qty": 0,
                        "entry_price": 0.0,
                        "entry_timestamp": ts,
                    }
                pos = self.options_positions[pos_key]
                total_cost = (pos["long_qty"] * pos["entry_price"]) + (fill_price * qty)
                pos["long_qty"] += qty
                if pos["long_qty"] > 0:
                    pos["entry_price"] = total_cost / pos["long_qty"]
                pos["entry_timestamp"] = ts
            else:  # SELL
                # For options selling, receive premium but pay charges
                self.portfolio_mgr.portfolio.cash += (fill_price * qty)
                self.portfolio_mgr.portfolio.cash -= charges["total_charges"]
                self.portfolio_mgr.portfolio.total_fees += charges["total_charges"]
                if pos_key not in self.options_positions:
                    self.options_positions[pos_key] = {
                        "symbol": symbol,
                        "expiry": expiry,
                        "strike": strike,
                        "option_type": option_type,
                        "lotsize": lotsize,
                        "long_qty": 0,
                        "short_qty": 0,
                        "entry_price": 0.0,
                        "entry_timestamp": ts,
                    }
                pos = self.options_positions[pos_key]
                total_value = (pos["short_qty"] * pos.get("short_entry_price", 0.0)) + (fill_price * qty)
                pos["short_qty"] += qty
                if pos["short_qty"] > 0:
                    pos["short_entry_price"] = total_value / pos["short_qty"]
                pos["entry_timestamp"] = ts

            trade = _OptionsTradeWrapper({
                "id": f"T-OPT-{uuid.uuid4().hex[:8].upper()}",
                "order_id": f"O-OPT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": ts,
                "symbol": symbol,
                "direction": action,
                "price": fill_price,
                "qty": qty,
                "value": fill_price * qty,
                "slippage": abs(fill_price - close_p) * qty,
                "brokerage": charges["brokerage"],
                "stt": charges["stt"],
                "exc_charges": charges["exchange_charges"],
                "gst": charges["gst"],
                "sebi_charges": charges["sebi_charges"],
                "stamp_duty": charges["stamp_duty"],
                "total_charges": charges["total_charges"],
                # Extra fields for options
                "instrument_type": "OPTION",
                "strike": strike,
                "option_type": option_type,
                "expiry": expiry,
                "charges_breakdown": charges,
            })
            trades.append(trade)
        return trades

    def _check_options_expiry(self, ts: str) -> List[Any]:
        """
        Check if any open options positions have reached expiry.
        At 15:25 on expiry day, close them at the last available candle price,
        determine ITM/OTM, and apply expiry-day charges.
        """
        trades: List[Any] = []
        current_date = str(ts)[:10]
        current_time = str(ts)[11:16]

        for pos_key, pos in list(self.options_positions.items()):
            if pos.get("expiry") != current_date:
                continue
            # Only close at or after 15:25 on expiry day
            if current_time < "15:25":
                continue
            # Skip fully closed positions (net zero)
            net_qty = pos.get("short_qty", 0) - pos.get("long_qty", 0)
            if net_qty == 0:
                continue
            if pos.get("long_qty", 0) == 0 and pos.get("short_qty", 0) == 0:
                continue

            symbol = pos["symbol"]
            strike = pos["strike"]
            option_type = pos["option_type"]
            lotsize = pos["lotsize"]
            expiry = pos["expiry"]

            # Get last available options candle price for the day
            df_opts = self.options_data_mgr.get_ohlc(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                from_dt=expiry,
                to_dt=expiry,
                interval="ONE_MINUTE",
            )
            if df_opts is not None and not df_opts.empty:
                last_price = float(df_opts.iloc[-1]["close"])
            else:
                # Fallback: use entry price if no data available
                last_price = pos.get("entry_price", 0.0)
                print(f"WARN: No expiry-day options data for {pos_key}; using entry price {last_price}")

            # Determine ITM from underlying spot
            underlying_spot = self._get_underlying_spot(symbol, ts)
            if underlying_spot is not None:
                if option_type == "CE":
                    is_itm = underlying_spot > strike
                else:  # PE
                    is_itm = underlying_spot < strike
            else:
                # Fallback: assume OTM if underlying data missing
                is_itm = False
                print(f"WARN: Could not determine ITM for {pos_key}; assuming OTM.")

            long_qty = pos.get("long_qty", 0)
            short_qty = pos.get("short_qty", 0)
            quantity_lots = (long_qty + short_qty) // lotsize if lotsize else 0

            if long_qty > 0:
                entry_price = pos.get("entry_price", 0.0)
                if is_itm:
                    realized_pnl = (last_price - entry_price) * long_qty
                    self.portfolio_mgr.portfolio.cash += last_price * long_qty
                else:
                    realized_pnl = -entry_price * long_qty
                    # No additional cash flow; premium was already paid at entry
                self.portfolio_mgr.portfolio.total_pnl += realized_pnl
                charges = calculate_options_charges(
                    transaction_type="SELL",  # exercising is treated as sell for STT
                    premium=last_price,
                    strike=strike,
                    lot_size=lotsize,
                    quantity_lots=quantity_lots,
                    is_expiry_day=True,
                    is_itm=is_itm,
                )
                self.portfolio_mgr.portfolio.cash -= charges["total_charges"]
                self.portfolio_mgr.portfolio.total_fees += charges["total_charges"]
                trade = _OptionsTradeWrapper({
                    "id": f"T-EXP-{uuid.uuid4().hex[:8].upper()}",
                    "order_id": "EXPIRY-SETTLE",
                    "timestamp": ts,
                    "symbol": symbol,
                    "direction": "SELL",
                    "price": last_price,
                    "qty": long_qty,
                    "value": last_price * long_qty,
                    "slippage": 0.0,
                    "brokerage": charges["brokerage"],
                    "stt": charges["stt"],
                    "exc_charges": charges["exchange_charges"],
                    "gst": charges["gst"],
                    "sebi_charges": charges["sebi_charges"],
                    "stamp_duty": charges["stamp_duty"],
                    "total_charges": charges["total_charges"],
                    "instrument_type": "OPTION",
                    "strike": strike,
                    "option_type": option_type,
                    "expiry": expiry,
                    "charges_breakdown": charges,
                })
                trades.append(trade)
                pos["long_qty"] = 0

            if short_qty > 0:
                short_entry_price = pos.get("short_entry_price", 0.0)
                if is_itm:
                    realized_pnl = (short_entry_price - last_price) * short_qty
                    self.portfolio_mgr.portfolio.cash -= last_price * short_qty
                else:
                    realized_pnl = short_entry_price * short_qty
                    # No additional cash flow; premium was already received at entry
                self.portfolio_mgr.portfolio.total_pnl += realized_pnl
                charges = calculate_options_charges(
                    transaction_type="BUY",  # assignment is treated as buy
                    premium=last_price,
                    strike=strike,
                    lot_size=lotsize,
                    quantity_lots=quantity_lots,
                    is_expiry_day=True,
                    is_itm=is_itm,
                )
                self.portfolio_mgr.portfolio.cash -= charges["total_charges"]
                self.portfolio_mgr.portfolio.total_fees += charges["total_charges"]
                trade = _OptionsTradeWrapper({
                    "id": f"T-EXP-{uuid.uuid4().hex[:8].upper()}",
                    "order_id": "EXPIRY-SETTLE",
                    "timestamp": ts,
                    "symbol": symbol,
                    "direction": "BUY",
                    "price": last_price,
                    "qty": short_qty,
                    "value": last_price * short_qty,
                    "slippage": 0.0,
                    "brokerage": charges["brokerage"],
                    "stt": charges["stt"],
                    "exc_charges": charges["exchange_charges"],
                    "gst": charges["gst"],
                    "sebi_charges": charges["sebi_charges"],
                    "stamp_duty": charges["stamp_duty"],
                    "total_charges": charges["total_charges"],
                    "instrument_type": "OPTION",
                    "strike": strike,
                    "option_type": option_type,
                    "expiry": expiry,
                    "charges_breakdown": charges,
                })
                trades.append(trade)
                pos["short_qty"] = 0

            # Clean up fully closed positions
            if pos.get("long_qty", 0) == 0 and pos.get("short_qty", 0) == 0:
                del self.options_positions[pos_key]

        return trades

    @staticmethod
    def _normalize_options_order(order_req: Any) -> Optional[Dict[str, Any]]:
        """Extract options fields from a submitted order dict/object."""
        if isinstance(order_req, dict):
            d = dict(order_req)
            if d.get("instrument_type", "").upper() != "OPTION":
                return None
            if "symbol" not in d or "expiry" not in d or "strike" not in d or "option_type" not in d:
                return None
            return {
                "symbol": d["symbol"],
                "expiry": d["expiry"],
                "strike": d["strike"],
                "option_type": d["option_type"].upper(),
                "action": d.get("action", d.get("direction", "BUY")),
                "quantity_lots": d.get("quantity_lots", d.get("qty", 1)),
                "lot_size": d.get("lot_size", 75),
            }
        if hasattr(order_req, "instrument_type"):
            if getattr(order_req, "instrument_type", "").upper() != "OPTION":
                return None
            return {
                "symbol": order_req.symbol,
                "expiry": getattr(order_req, "expiry", ""),
                "strike": getattr(order_req, "strike", 0.0),
                "option_type": getattr(order_req, "option_type", "").upper(),
                "action": getattr(order_req, "action", getattr(order_req, "direction", "BUY")),
                "quantity_lots": getattr(order_req, "quantity_lots", getattr(order_req, "qty", 1)),
                "lot_size": getattr(order_req, "lot_size", 75),
            }
        return None

    def run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute backtest over all timestamps.

        Returns dict with run_id, trades, equity_curve, final_portfolio, log_file_path.
        """
        if not run_id:
            run_id = f"B-{uuid.uuid4().hex[:8].upper()}"

        log_file_path = os.path.join(self.log_dir, f"{run_id}.jsonl")

        all_trades: List[Any] = []
        equity_curve: List[Dict[str, Any]] = []
        trader_data_json = "{}"
        own_trades_by_symbol: Dict[str, List[RTrade]] = {sym: [] for sym in self.df_dict.keys()}
        current_prices: Dict[str, float] = {}

        with ReplayLogger(log_file_path) as logger:
            for step, ts in enumerate(self.all_timestamps):
                # ===== PHASE 1: Gather market data =====
                current_candles: Dict[str, Any] = {}
                order_depths = {}

                for symbol, df in self.df_dict.items():
                    mask = df['time'].astype(str) == ts
                    rows = df[mask]
                    if not rows.empty:
                        row = rows.iloc[0]
                        current_candles[symbol] = row
                        current_prices[symbol] = float(row['close'])
                        od = self.order_book_adapter.candle_to_order_depth(symbol, row)
                        order_depths[symbol] = od

                if not current_candles:
                    continue

                # Accumulate historical candles for legacy strategies
                for symbol, row in current_candles.items():
                    candle = Candle(
                        time=str(ts),
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(row.get('volume', 0)),
                        open_interest=int(row.get('open_interest', 0)),
                    )
                    self.historical_candles[symbol].append(candle)
                    if len(self.historical_candles[symbol]) > 2000:
                        self.historical_candles[symbol] = self.historical_candles[symbol][-2000:]

                # ===== PHASE 2: Match pending orders =====
                filled_trades, match_rtrades = self.order_mgr.match_pending_orders(
                    current_candles=current_candles,
                    timestamp=ts,
                    current_positions=self.portfolio_mgr.portfolio.positions,
                )
                for trade in filled_trades:
                    all_trades.append(trade)
                    self.portfolio_mgr.apply_trade(trade)
                    own_trades_by_symbol[trade.symbol].append(RTrade(
                        symbol=trade.symbol,
                        price=trade.price,
                        quantity=trade.qty,
                        timestamp=ts,
                        direction=trade.direction,
                        trade_id=trade.id,
                    ))

                self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
                    self.portfolio_mgr.portfolio.positions
                )

                # ===== PHASE 3: Mark to market =====
                self.portfolio_mgr.mark_to_market(current_prices)

                # ===== PHASE 4: Margin call / liquidation =====
                if self.portfolio_mgr.is_margin_call():
                    liq_trades = self.portfolio_mgr.liquidate_all(
                        current_prices=current_prices,
                        timestamp=ts,
                        execution_sim=self.execution_sim,
                    )
                    for trade in liq_trades:
                        all_trades.append(trade)
                        filled_trades.append(trade)
                        own_trades_by_symbol[trade.symbol].append(RTrade(
                            symbol=trade.symbol,
                            price=trade.price,
                            quantity=trade.qty,
                            timestamp=ts,
                            direction=trade.direction,
                            trade_id=trade.id,
                        ))

                # ===== PHASE 5: Build state and execute strategy =====
                positions_for_state = PortfolioStateBuilder.convert_backtest_positions(
                    self.portfolio_mgr.portfolio.positions,
                    current_prices
                )
                own_trades_state = {sym: trades[-100:] for sym, trades in own_trades_by_symbol.items()}

                trading_state = PortfolioStateBuilder.build_trading_state(
                    timestamp=ts,
                    order_depths=order_depths,
                    own_trades=own_trades_state,
                    market_trades={sym: [] for sym in self.df_dict.keys()},
                    positions=positions_for_state,
                    portfolio_equity=self.portfolio_mgr.portfolio.equity,
                    portfolio_cash=self.portfolio_mgr.portfolio.cash,
                    trader_data=trader_data_json,
                )

                submitted_orders = []
                if self.portfolio_mgr.portfolio.equity > 0:
                    if isinstance(self.runtime, LegacyRuntime):
                        current_candle_dict = {
                            sym: Candle(
                                time=str(ts),
                                open=float(row['open']),
                                high=float(row['high']),
                                low=float(row['low']),
                                close=float(row['close']),
                                volume=int(row.get('volume', 0)),
                                open_interest=int(row.get('open_interest', 0)),
                            )
                            for sym, row in current_candles.items()
                        }
                        market_state = MarketState(
                            current_time=ts,
                            current_candle=current_candle_dict,
                            historical_candles={sym: list(candles) for sym, candles in self.historical_candles.items()},
                            positions=self.portfolio_mgr.portfolio.positions,
                            portfolio=self.portfolio_mgr.portfolio,
                            active_orders=self.order_mgr.active_orders,
                        )
                        submitted_orders, trader_data_json = self.runtime.on_tick(market_state)
                    else:
                        submitted_orders, trader_data_json = self.runtime.on_tick(trading_state)

                strategy_logs_json = self.runtime.get_logs()

                # ===== PHASE 6: Process new orders =====
                # Split equity and options orders
                equity_orders = [o for o in submitted_orders if not self._is_options_order(o)]
                options_orders = [o for o in submitted_orders if self._is_options_order(o)]

                new_orders, new_filled, new_rtrades = self.order_mgr.process_submitted_orders(
                    submitted_orders=equity_orders,
                    current_candles=current_candles,
                    timestamp=ts,
                    current_positions=self.portfolio_mgr.portfolio.positions,
                )
                for trade in new_filled:
                    all_trades.append(trade)
                    filled_trades.append(trade)
                    self.portfolio_mgr.apply_trade(trade)
                    own_trades_by_symbol[trade.symbol].append(RTrade(
                        symbol=trade.symbol,
                        price=trade.price,
                        quantity=trade.qty,
                        timestamp=ts,
                        direction=trade.direction,
                        trade_id=trade.id,
                    ))

                # Process options orders
                if options_orders:
                    opt_trades = self._process_options_orders(options_orders, ts)
                    for trade in opt_trades:
                        all_trades.append(trade)
                        filled_trades.append(trade)

                # ===== PHASE 6.5: Check options expiry =====
                expiry_trades = self._check_options_expiry(ts)
                for trade in expiry_trades:
                    all_trades.append(trade)
                    filled_trades.append(trade)

                # ===== PHASE 7: Finalize =====
                self.portfolio_mgr.mark_to_market(current_prices)

                # ===== PHASE 7.5: EOD intraday squaring =====
                # In Indian markets, intraday positions must be squared off by end of trading day.
                is_last_candle_of_day = False
                if step + 1 < len(self.all_timestamps):
                    next_ts = self.all_timestamps[step + 1]
                    current_date = str(ts)[:10]
                    next_date = str(next_ts)[:10]
                    is_last_candle_of_day = current_date != next_date
                else:
                    is_last_candle_of_day = True

                if is_last_candle_of_day and self.default_trade_type == "INTRADAY":
                    if self.portfolio_mgr.portfolio.positions:
                        eod_liq_trades = self.portfolio_mgr.liquidate_all(
                            current_prices=current_prices,
                            timestamp=ts,
                            execution_sim=self.execution_sim,
                        )
                        for trade in eod_liq_trades:
                            all_trades.append(trade)
                            filled_trades.append(trade)
                            own_trades_by_symbol[trade.symbol].append(RTrade(
                                symbol=trade.symbol,
                                price=trade.price,
                                quantity=trade.qty,
                                timestamp=ts,
                                direction=trade.direction,
                                trade_id=trade.id,
                            ))

                # Take snapshot BEFORE pruning zero positions so realized_pnl is preserved in the log
                portfolio_snapshot = self.portfolio_mgr.get_snapshot()

                self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
                    self.portfolio_mgr.portfolio.positions
                )

                # ===== PHASE 8: Equity curve & replay event =====
                equity_curve.append({
                    "time": ts,
                    "equity": self.portfolio_mgr.portfolio.equity,
                    "cash": self.portfolio_mgr.portfolio.cash,
                    "unrealized_pnl": self.portfolio_mgr.portfolio.unrealized_pnl,
                    "margin_used": self.portfolio_mgr.portfolio.margin_used,
                    "fees": self.portfolio_mgr.portfolio.total_fees,
                    "position_count": len(self.portfolio_mgr.portfolio.positions) + len(self.options_positions),
                    "total_qty": (
                        sum(abs(p.qty) for p in self.portfolio_mgr.portfolio.positions.values()) +
                        sum(abs(pos.get("long_qty", 0)) + abs(pos.get("short_qty", 0)) for pos in self.options_positions.values())
                    ),
                    "trader_data": trader_data_json,
                })

                orders_filled_dicts = [
                    {"symbol": t.symbol, "direction": t.direction, "price": t.price,
                     "qty": t.qty, "timestamp": t.timestamp, "charges": t.total_charges}
                    for t in filled_trades
                ]
                orders_submitted_dicts = [
                    {"symbol": o.symbol, "direction": o.direction, "price": o.price, "quantity": o.qty}
                    for o in new_orders
                ]

                replay_event = ReplayLogger.build_event(
                    step=step,
                    timestamp=ts,
                    trading_state=trading_state,
                    orders_submitted=orders_submitted_dicts,
                    orders_filled=orders_filled_dicts,
                    strategy_logs=strategy_logs_json,
                    portfolio_snapshot=portfolio_snapshot,
                    current_candles=current_candles,
                )
                logger.write_event(replay_event)

        # Determine final pricing mode
        if not self._used_bsm_contracts:
            self.pricing_mode = "REAL_DATA"
        else:
            self.pricing_mode = "BSM_APPROXIMATION"

        return {
            "run_id": run_id,
            "pricing_mode": self.pricing_mode,
            "used_real_data_contracts": list(self._used_real_data_contracts),
            "used_bsm_contracts": list(self._used_bsm_contracts),
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "price": t.price,
                    "qty": t.qty,
                    "timestamp": str(t.timestamp),
                    "brokerage": t.brokerage,
                    "stt": t.stt,
                    "exc_charges": t.exc_charges,
                    "gst": t.gst,
                    "sebi_charges": t.sebi_charges,
                    "stamp_duty": t.stamp_duty,
                    "total_charges": t.total_charges,
                    "instrument_type": getattr(t, "instrument_type", "EQUITY"),
                    "strike": getattr(t, "strike", None),
                    "option_type": getattr(t, "option_type", None),
                    "expiry": getattr(t, "expiry", None),
                    "charges_breakdown": getattr(t, "charges_breakdown", None),
                }
                for t in all_trades
            ],
            "equity_curve": equity_curve,
            "final_portfolio": {
                "equity": self.portfolio_mgr.portfolio.equity,
                "cash": self.portfolio_mgr.portfolio.cash,
                "total_pnl": self.portfolio_mgr.portfolio.total_pnl,
                "total_fees": self.portfolio_mgr.portfolio.total_fees,
                "positions": len(self.portfolio_mgr.portfolio.positions) + len(self.options_positions),
            },
            "log_file_path": log_file_path,
        }

    def _is_options_order(self, order_req: Any) -> bool:
        """Return True if the submitted order is an options contract order."""
        if isinstance(order_req, dict):
            return order_req.get("instrument_type", "").upper() == "OPTION"
        if hasattr(order_req, "instrument_type"):
            return getattr(order_req, "instrument_type", "").upper() == "OPTION"
        return False
