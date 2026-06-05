import os
import json
import uuid
from typing import List, Dict, Any, Optional
import pandas as pd
from engine.datamodels import (
    Candle, Order, OrderRequest, Trade, Position, Portfolio, MarketState, ReplayEvent, BacktestRunMetadata
)
from engine.execution import ExecutionSimulator
from engine.runtime import SandboxedStrategyRuntime

class BacktestEngine:
    def __init__(
        self,
        df_dict: Dict[str, pd.DataFrame],  # symbol -> DataFrame with Columns [time, open, high, low, close, volume, open_interest]
        strategy_code: str,
        initial_capital: float = 100000.0,
        slippage_pct: float = 0.0005,
        default_trade_type: str = "INTRADAY",
        log_dir: str = "./logs",
        parameters: Optional[Dict[str, Any]] = None
    ):
        self.df_dict = df_dict
        self.strategy_code = strategy_code
        self.initial_capital = initial_capital
        self.log_dir = log_dir
        
        # Init components
        self.execution_sim = ExecutionSimulator(
            slippage_pct=slippage_pct,
            default_trade_type=default_trade_type
        )
        self.runtime = SandboxedStrategyRuntime(strategy_code, parameters=parameters)

        # Set up log dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Determine margins based on trade type
        self.margin_multiplier = 0.20  # 5x leverage for INTRADAY
        if default_trade_type == "DELIVERY":
            self.margin_multiplier = 1.0  # 1x leverage
        elif default_trade_type == "FUTURES":
            self.margin_multiplier = 0.15  # ~6.6x leverage for F&O

        # Alignment of timestamps across symbols (outer join or index matching)
        self.all_timestamps = self._align_timestamps()

    def _align_timestamps(self) -> List[str]:
        """Collects and sorts all unique timestamps across symbols."""
        timestamps = set()
        for symbol, df in self.df_dict.items():
            if 'time' in df.columns:
                timestamps.update(df['time'].astype(str).tolist())
            elif isinstance(df.index, pd.DatetimeIndex):
                timestamps.update(df.index.strftime('%Y-%m-%d %H:%M:%S').tolist())
        return sorted(list(timestamps))

    def run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Runs the backtest simulation over all timestamps."""
        if not run_id:
            run_id = f"B-{uuid.uuid4().hex[:8].upper()}"

        log_file_path = os.path.join(self.log_dir, f"{run_id}.jsonl")
        
        # Initial Portfolio State
        portfolio = Portfolio(
            cash=self.initial_capital,
            margin_used=0.0,
            margin_free=self.initial_capital,
            equity=self.initial_capital,
            positions={},
            total_fees=0.0,
            total_pnl=0.0
        )
        
        active_orders: List[Order] = []
        all_trades: List[Trade] = []
        equity_curve: List[Dict[str, Any]] = []
        
        # Track sliding window of candles for strategy reference
        historical_candles: Dict[str, List[Candle]] = {sym: [] for sym in self.df_dict.keys()}

        # Open JSONL log file for streaming step logs
        with open(log_file_path, "w") as log_file:
            for step, ts in enumerate(self.all_timestamps):
                # 1. Gather current candle for this timestamp
                current_candles: Dict[str, Candle] = {}
                for symbol, df in self.df_dict.items():
                    # Find candle for ts
                    # Assumes df has time column or indexed by time string
                    mask = df['time'].astype(str) == ts
                    rows = df[mask]
                    if not rows.empty:
                        row = rows.iloc[0]
                        candle = Candle(
                            time=ts,
                            open=float(row['open']),
                            high=float(row['high']),
                            low=float(row['low']),
                            close=float(row['close']),
                            volume=int(row['volume']),
                            open_interest=int(row.get('open_interest', 0))
                        )
                        current_candles[symbol] = candle
                        historical_candles[symbol].append(candle)
                
                if not current_candles:
                    continue  # Skip steps where no candles exist

                # 2. Process / Match Pending Orders
                filled_trades_this_step: List[Trade] = []
                remaining_orders: List[Order] = []

                for order in active_orders:
                    if order.symbol in current_candles:
                        candle = current_candles[order.symbol]
                        trade = self.execution_sim.match_order(order, candle, ts)
                        if trade:
                            filled_trades_this_step.append(trade)
                            all_trades.append(trade)
                            
                            # Update Portfolio Positions & Cash
                            pos_sym = order.symbol
                            if pos_sym not in portfolio.positions:
                                portfolio.positions[pos_sym] = Position(symbol=pos_sym)

                            pos = portfolio.positions[pos_sym]
                            direction_multiplier = 1 if trade.direction == "BUY" else -1
                            
                            # Calculations for realized PnL
                            current_qty = pos.qty
                            trade_qty = trade.qty
                            
                            # If adding to position, average cost updates
                            if (current_qty >= 0 and direction_multiplier == 1) or (current_qty <= 0 and direction_multiplier == -1):
                                total_cost = (pos.qty * pos.avg_price) + (trade.price * trade.qty * direction_multiplier)
                                pos.qty += trade.qty * direction_multiplier
                                if pos.qty != 0:
                                    pos.avg_price = abs(total_cost / pos.qty)
                            else:
                                # Closing or reducing position
                                matched_qty = min(abs(current_qty), trade_qty)
                                pnl = (trade.price - pos.avg_price) * matched_qty * (1 if current_qty > 0 else -1)
                                pos.realized_pnl += pnl
                                portfolio.total_pnl += pnl
                                
                                # Remainder of trade
                                pos.qty += trade.qty * direction_multiplier
                                remaining_qty = trade_qty - matched_qty
                                if remaining_qty > 0 and pos.qty != 0:
                                    # Position reversed direction
                                    pos.avg_price = trade.price
                                    
                            # Subtract fees
                            portfolio.cash -= trade.total_charges
                            portfolio.total_fees += trade.total_charges
                        else:
                            remaining_orders.append(order)
                    else:
                        remaining_orders.append(order)

                active_orders = remaining_orders

                # Remove empty positions
                portfolio.positions = {k: v for k, v in portfolio.positions.items() if v.qty != 0}

                # 3. Calculate Unrealized PnL and Update Portfolio Equity
                unrealized_pnl = 0.0
                margin_used = 0.0
                for sym, pos in portfolio.positions.items():
                    if sym in current_candles:
                        close_price = current_candles[sym].close
                        pos.unrealized_pnl = (close_price - pos.avg_price) * pos.qty
                        unrealized_pnl += pos.unrealized_pnl
                        # Margin requirement calculation
                        margin_used += abs(pos.qty) * pos.avg_price * self.margin_multiplier
                
                portfolio.unrealized_pnl = unrealized_pnl
                portfolio.equity = portfolio.cash + unrealized_pnl
                portfolio.margin_used = margin_used
                portfolio.margin_free = portfolio.equity - margin_used

                # 4. Check Margin Call / Liquidation (Risk of Ruin)
                if portfolio.equity <= 0 or portfolio.margin_free < 0:
                    # Liquidation Trigger
                    liquidation_logs = ["MARGIN CALL: Liquidating all positions and cancelling pending orders!"]
                    active_orders.clear()
                    # Liquidate positions at current candle closes
                    for sym, pos in list(portfolio.positions.items()):
                        close_p = current_candles[sym].close if sym in current_candles else pos.avg_price
                        liq_dir = "SELL" if pos.qty > 0 else "BUY"
                        qty = abs(pos.qty)
                        
                        # Generate trade representing liquidation
                        _, _, _, _, _, _, fee = self.execution_sim.calculate_charges(sym, liq_dir, close_p, qty)
                        real_p = (close_p - pos.avg_price) * pos.qty
                        portfolio.cash += (close_p * pos.qty) - fee  # Rough cash adjustment
                        portfolio.total_pnl += real_p
                        portfolio.total_fees += fee
                        
                        trades_liq = Trade(
                            id=f"T-LIQ-{uuid.uuid4().hex[:6].upper()}",
                            order_id="LIQUIDATION",
                            timestamp=ts,
                            symbol=sym,
                            direction=liq_dir,
                            price=close_p,
                            qty=qty,
                            value=close_p * qty,
                            total_charges=fee
                        )
                        all_trades.append(trades_liq)
                        filled_trades_this_step.append(trades_liq)
                    
                    portfolio.positions.clear()
                    portfolio.margin_used = 0.0
                    portfolio.margin_free = portfolio.cash
                    portfolio.unrealized_pnl = 0.0
                    portfolio.equity = portfolio.cash

                # 5. Populate and execute the sandboxed strategy bar update
                state = MarketState(
                    current_time=ts,
                    current_candle=current_candles,
                    historical_candles={k: list(v[-100:]) for k, v in historical_candles.items()},  # Limit history to sliding window of 100 bars for performance
                    positions=portfolio.positions,
                    portfolio=portfolio,
                    active_orders=active_orders
                )

                # Execute logic
                submitted_order_reqs = []
                if portfolio.equity > 0:  # Only execute if not bankrupt
                    submitted_order_reqs = self.runtime.on_bar(state)

                # Process submitted orders
                strategy_logs = self.runtime.get_logs()
                
                # Append liquidation logs if triggered
                if 'liquidation_logs' in locals():
                    strategy_logs.extend(liquidation_logs)
                    del liquidation_logs

                new_orders: List[Order] = []
                for req in submitted_order_reqs:
                    # Construct Order
                    order_id = f"O-{uuid.uuid4().hex[:8].upper()}"
                    new_order = Order(
                        id=order_id,
                        symbol=req.symbol,
                        direction=req.direction,
                        type=req.type,
                        price=req.price,
                        qty=req.qty,
                        status="PENDING",
                        trigger_price=req.trigger_price,
                        created_at=ts
                    )
                    
                    # Handle IMMEDIATE MARKET execution simulation (end of bar execution)
                    if new_order.type == "MARKET" and new_order.symbol in current_candles:
                        candle = current_candles[new_order.symbol]
                        trade = self.execution_sim.match_order(new_order, candle, ts)
                        if trade:
                            filled_trades_this_step.append(trade)
                            all_trades.append(trade)
                            
                            # Position accounting
                            pos_sym = new_order.symbol
                            if pos_sym not in portfolio.positions:
                                portfolio.positions[pos_sym] = Position(symbol=pos_sym)
                            pos = portfolio.positions[pos_sym]
                            direction_multiplier = 1 if trade.direction == "BUY" else -1
                            
                            current_qty = pos.qty
                            trade_qty = trade.qty
                            
                            if (current_qty >= 0 and direction_multiplier == 1) or (current_qty <= 0 and direction_multiplier == -1):
                                total_cost = (pos.qty * pos.avg_price) + (trade.price * trade.qty * direction_multiplier)
                                pos.qty += trade.qty * direction_multiplier
                                if pos.qty != 0:
                                    pos.avg_price = abs(total_cost / pos.qty)
                            else:
                                matched_qty = min(abs(current_qty), trade_qty)
                                pnl = (trade.price - pos.avg_price) * matched_qty * (1 if current_qty > 0 else -1)
                                pos.realized_pnl += pnl
                                portfolio.total_pnl += pnl
                                
                                pos.qty += trade.qty * direction_multiplier
                                remaining_qty = trade_qty - matched_qty
                                if remaining_qty > 0 and pos.qty != 0:
                                    pos.avg_price = trade.price
                                    
                            portfolio.cash -= trade.total_charges
                            portfolio.total_fees += trade.total_charges
                    else:
                        # Queue limit orders for matching on future candles
                        active_orders.append(new_order)
                    
                    new_orders.append(new_order)

                # Recalculate portfolio totals after market orders have executed
                unrealized_pnl = 0.0
                margin_used = 0.0
                for sym, pos in list(portfolio.positions.items()):
                    if pos.qty == 0:
                        continue
                    if sym in current_candles:
                        close_price = current_candles[sym].close
                        pos.unrealized_pnl = (close_price - pos.avg_price) * pos.qty
                        unrealized_pnl += pos.unrealized_pnl
                        margin_used += abs(pos.qty) * pos.avg_price * self.margin_multiplier

                portfolio.positions = {k: v for k, v in portfolio.positions.items() if v.qty != 0}
                portfolio.unrealized_pnl = unrealized_pnl
                portfolio.equity = portfolio.cash + unrealized_pnl
                portfolio.margin_used = margin_used
                portfolio.margin_free = portfolio.equity - margin_used
                
                # Equity curve snapshot
                equity_curve.append({
                    "time": ts,
                    "equity": portfolio.equity,
                    "cash": portfolio.cash,
                    "unrealized_pnl": portfolio.unrealized_pnl,
                    "margin_used": portfolio.margin_used,
                    "fees": portfolio.total_fees
                })

                # Create ReplayEvent
                event = ReplayEvent(
                    step=step,
                    timestamp=ts,
                    candle=current_candles,
                    orders_submitted=submitted_order_reqs,
                    orders_filled=filled_trades_this_step,
                    portfolio=portfolio.model_copy(deep=True),
                    log_messages=strategy_logs
                )
                
                # Write to jsonl
                log_file.write(event.model_dump_json() + "\n")

        # Create final response
        return {
            "run_id": run_id,
            "trades": [t.model_dump() for t in all_trades],
            "equity_curve": equity_curve,
            "final_portfolio": portfolio.model_dump(),
            "log_file_path": log_file_path
        }
