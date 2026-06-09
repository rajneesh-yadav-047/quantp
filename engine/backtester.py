"""
Event-driven backtesting engine with Prosperity runtime integration.

Updated architecture:
- Builds TradingState each tick (instead of raw DataFrame rows)
- Uses RuntimeFactory to select strategy runtime (Prosperity or Legacy)
- Persists trader_data across ticks
- Generates synthetic OrderDepths from candles via CandleToOrderBookAdapter
- Produces structured replay events for frontend consumption
"""

import os
import json
import uuid
from typing import List, Dict, Any, Optional
import pandas as pd

from engine.datamodels import (
    Trade, Position, Portfolio
)
from engine.execution import ExecutionSimulator
from engine.runtime.runtimes import RuntimeFactory
from engine.runtime.adapters import (
    CandleToOrderBookAdapter,
    PortfolioStateBuilder,
    ReplayEventBuilder,
)
from engine.runtime.datamodels import (
    Order, Trade as RTrade, TradingState, OrderDepth
)


class BacktestEngine:
    """
    Event-driven backtester with Prosperity-compatible strategy runtime.
    
    Responsibilities:
    1. Align timestamps across symbols
    2. Each tick: build TradingState and execute strategy
    3. Persist trader_data between ticks
    4. Match orders and calculate P&L
    5. Detect margin calls and liquidate
    6. Generate replay events for frontend
    """

    def __init__(
        self,
        df_dict: Dict[str, pd.DataFrame],  # symbol -> DataFrame [time, open, high, low, close, volume, open_interest]
        strategy_code: str,
        initial_capital: float = 100000.0,
        slippage_pct: float = 0.0005,
        default_trade_type: str = "INTRADAY",
        max_position_size: Optional[int] = None,
        log_dir: str = "./logs",
        parameters: Optional[Dict[str, Any]] = None,
        runtime_type: Optional[str] = None,  # "prosperity_trader" or "legacy_on_bar"
        spread_pct: float = 0.01,  # for synthetic order book
    ):
        """
        Args:
            df_dict: Dict[symbol -> DataFrame]
            strategy_code: full source code
            initial_capital: starting portfolio value
            slippage_pct: execution slippage (0.05% = 0.0005)
            default_trade_type: "INTRADAY", "DELIVERY", or "FUTURES"
            max_position_size: cap position size
            log_dir: where to write JSONL replay logs
            parameters: optional parameter overrides (for optimization)
            runtime_type: "prosperity_trader", "legacy_on_bar", or None (auto-detect)
            spread_pct: bid-ask spread for synthetic order books
        """
        self.df_dict = df_dict
        self.strategy_code = strategy_code
        self.initial_capital = initial_capital
        self.max_position_size = max_position_size
        self.log_dir = log_dir
        self.runtime_type = runtime_type

        # Components
        self.execution_sim = ExecutionSimulator(
            slippage_pct=slippage_pct,
            default_trade_type=default_trade_type
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

        # Setup log directory
        os.makedirs(self.log_dir, exist_ok=True)

        # Margin multiplier based on trade type
        self.margin_multiplier = 0.20  # 5x leverage for INTRADAY
        if default_trade_type == "DELIVERY":
            self.margin_multiplier = 1.0
        elif default_trade_type == "FUTURES":
            self.margin_multiplier = 0.15  # ~6.6x leverage

        # Align timestamps
        self.all_timestamps = self._align_timestamps()

    def _align_timestamps(self) -> List[str]:
        """Collect and sort all unique timestamps across symbols."""
        timestamps = set()
        for symbol, df in self.df_dict.items():
            if 'time' in df.columns:
                timestamps.update(df['time'].astype(str).tolist())
            elif isinstance(df.index, pd.DatetimeIndex):
                timestamps.update(df.index.strftime('%Y-%m-%d %H:%M:%S').tolist())
        return sorted(list(timestamps))

    def run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute backtest over all timestamps.

        Returns dict with:
        - run_id: identifier
        - trades: all trades executed
        - equity_curve: portfolio value over time
        - final_portfolio: end state
        - log_file_path: JSONL replay events
        """
        if not run_id:
            run_id = f"B-{uuid.uuid4().hex[:8].upper()}"

        log_file_path = os.path.join(self.log_dir, f"{run_id}.jsonl")

        # Initialize portfolio
        portfolio = Portfolio(
            cash=self.initial_capital,
            margin_used=0.0,
            margin_free=self.initial_capital,
            equity=self.initial_capital,
            positions={},
            total_fees=0.0,
            total_pnl=0.0
        )

        active_orders: List = []
        all_trades: List[Trade] = []
        equity_curve: List[Dict[str, Any]] = []

        # Strategy memory: persisted across ticks
        trader_data_json = "{}"

        # Track own trades and market trades for TradingState
        own_trades_by_symbol: Dict[str, List[RTrade]] = {sym: [] for sym in self.df_dict.keys()}
        market_trades_by_symbol: Dict[str, List[RTrade]] = {sym: [] for sym in self.df_dict.keys()}

        # Current prices for unrealized P&L
        current_prices: Dict[str, float] = {}

        with open(log_file_path, "w") as log_file:
            for step, ts in enumerate(self.all_timestamps):
                # ===== PHASE 1: Gather market data =====
                current_candles: Dict[str, Any] = {}
                order_depths: Dict[str, OrderDepth] = {}

                for symbol, df in self.df_dict.items():
                    mask = df['time'].astype(str) == ts
                    rows = df[mask]
                    if not rows.empty:
                        row = rows.iloc[0]
                        current_candles[symbol] = row
                        current_prices[symbol] = float(row['close'])

                        # Generate synthetic order book from candle
                        od = self.order_book_adapter.candle_to_order_depth(symbol, row)
                        order_depths[symbol] = od

                if not current_candles:
                    continue  # No data at this timestamp

                # ===== PHASE 2: Match pending orders =====
                filled_trades_this_step: List[Trade] = []
                remaining_orders: List = []

                for order in active_orders:
                    if order.symbol in current_candles:
                        trade = self.execution_sim.match_order(order, current_candles[order.symbol], ts)
                        if trade:
                            filled_trades_this_step.append(trade)
                            all_trades.append(trade)

                            # Convert to RTrade for TradingState
                            rtrade = RTrade(
                                symbol=trade.symbol,
                                price=trade.price,
                                quantity=trade.qty,
                                timestamp=ts,
                                direction=trade.direction,
                                trade_id=trade.id
                            )
                            own_trades_by_symbol[trade.symbol].append(rtrade)

                            # Update portfolio
                            self._update_portfolio_from_trade(portfolio, trade)
                        else:
                            remaining_orders.append(order)
                    else:
                        remaining_orders.append(order)

                active_orders = remaining_orders
                portfolio.positions = {k: v for k, v in portfolio.positions.items() if v.qty != 0}

                # ===== PHASE 3: Update portfolio state =====
                self._update_portfolio_unrealized(portfolio, current_prices)

                # ===== PHASE 4: Margin call / liquidation check =====
                liquidation_logs: List[str] = []
                if portfolio.equity <= 0 or portfolio.margin_free < 0:
                    liquidation_logs = self._liquidate_positions(
                        portfolio, current_candles, current_prices, ts, all_trades, filled_trades_this_step
                    )

                # ===== PHASE 5: Build TradingState and execute strategy =====
                positions_for_state = PortfolioStateBuilder.convert_backtest_positions(
                    portfolio.positions,
                    current_prices
                )

                # Limit own_trades to last 100 per symbol for performance
                own_trades_state = {
                    sym: trades[-100:] for sym, trades in own_trades_by_symbol.items()
                }

                trading_state = PortfolioStateBuilder.build_trading_state(
                    timestamp=ts,
                    order_depths=order_depths,
                    own_trades=own_trades_state,
                    market_trades={sym: [] for sym in self.df_dict.keys()},  # TODO: populate from real market data
                    positions=positions_for_state,
                    portfolio_equity=portfolio.equity,
                    portfolio_cash=portfolio.cash,
                    trader_data=trader_data_json,
                )

                # Execute strategy
                submitted_orders = []
                if portfolio.equity > 0:
                    submitted_orders, trader_data_json = self.runtime.on_tick(trading_state)

                # Get strategy logs
                strategy_logs_json = self.runtime.get_logs()

                # ===== PHASE 6: Process new orders =====
                new_orders: List = []
                for order_req in submitted_orders:
                    order_id = f"O-{uuid.uuid4().hex[:8].upper()}"

                    # Cap by max_position_size
                    final_qty = order_req.quantity
                    if self.max_position_size and self.max_position_size > 0:
                        final_qty = min(order_req.quantity, self.max_position_size)

                    new_order = self._create_order(
                        order_id=order_id,
                        symbol=order_req.symbol,
                        direction=order_req.direction,
                        price=order_req.price,
                        qty=final_qty,
                        ts=ts
                    )

                    # MARKET orders execute immediately
                    if order_req.type == "MARKET" and order_req.symbol in current_candles:
                        trade = self.execution_sim.match_order(new_order, current_candles[order_req.symbol], ts)
                        if trade:
                            filled_trades_this_step.append(trade)
                            all_trades.append(trade)

                            rtrade = RTrade(
                                symbol=trade.symbol,
                                price=trade.price,
                                quantity=trade.qty,
                                timestamp=ts,
                                direction=trade.direction,
                                trade_id=trade.id
                            )
                            own_trades_by_symbol[trade.symbol].append(rtrade)
                            self._update_portfolio_from_trade(portfolio, trade)
                    else:
                        # LIMIT orders queue for future matching
                        active_orders.append(new_order)

                    new_orders.append(new_order)

                # ===== PHASE 7: Finalize portfolio state =====
                self._update_portfolio_unrealized(portfolio, current_prices)

                # ===== PHASE 8: Generate replay event =====
                equity_curve.append({
                    "time": ts,
                    "equity": portfolio.equity,
                    "cash": portfolio.cash,
                    "unrealized_pnl": portfolio.unrealized_pnl,
                    "margin_used": portfolio.margin_used,
                    "fees": portfolio.total_fees,
                    "position_count": len(portfolio.positions),
                    "total_qty": sum(abs(p.qty) for p in portfolio.positions.values()),
                    "trader_data": trader_data_json,  # Include strategy memory in equity curve
                })

                # Convert trades to dicts for logging
                orders_filled_dicts = [
                    {
                        "symbol": t.symbol,
                        "direction": t.direction,
                        "price": t.price,
                        "qty": t.qty,
                        "timestamp": t.timestamp,
                        "charges": t.total_charges,
                    }
                    for t in filled_trades_this_step
                ]

                orders_submitted_dicts = [
                    {
                        "symbol": o.symbol,
                        "direction": o.direction,
                        "price": o.price,
                        "quantity": o.quantity,
                    }
                    for o in submitted_orders
                ]

                replay_event = ReplayEventBuilder.build_replay_event(
                    step=step,
                    timestamp=ts,
                    trading_state=trading_state,
                    orders_submitted=orders_submitted_dicts,
                    orders_filled=orders_filled_dicts,
                    strategy_logs=strategy_logs_json,
                )

                # Write JSONL
                log_file.write(json.dumps(replay_event) + "\n")

        return {
            "run_id": run_id,
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "price": t.price,
                    "qty": t.qty,
                    "timestamp": t.timestamp,
                    "charges": t.total_charges,
                }
                for t in all_trades
            ],
            "equity_curve": equity_curve,
            "final_portfolio": {
                "equity": portfolio.equity,
                "cash": portfolio.cash,
                "total_pnl": portfolio.total_pnl,
                "total_fees": portfolio.total_fees,
                "positions": len(portfolio.positions),
            },
            "log_file_path": log_file_path,
        }

    def _update_portfolio_from_trade(self, portfolio: Portfolio, trade: Trade):
        """Update portfolio positions and cash from a trade."""
        pos_sym = trade.symbol
        if pos_sym not in portfolio.positions:
            portfolio.positions[pos_sym] = Position(symbol=pos_sym)

        pos = portfolio.positions[pos_sym]
        direction_multiplier = 1 if trade.direction == "BUY" else -1

        current_qty = pos.qty
        trade_qty = trade.qty

        # Adding to position
        if (current_qty >= 0 and direction_multiplier == 1) or (current_qty <= 0 and direction_multiplier == -1):
            total_cost = (pos.qty * pos.avg_price) + (trade.price * trade.qty * direction_multiplier)
            pos.qty += trade.qty * direction_multiplier
            if pos.qty != 0:
                pos.avg_price = abs(total_cost / pos.qty)
        else:
            # Closing or reducing
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

    def _update_portfolio_unrealized(self, portfolio: Portfolio, current_prices: Dict[str, float]):
        """Mark positions to market and update unrealized P&L."""
        unrealized_pnl = 0.0
        margin_used = 0.0

        for sym, pos in portfolio.positions.items():
            close_price = current_prices.get(sym, pos.avg_price)
            pos.unrealized_pnl = (close_price - pos.avg_price) * pos.qty
            unrealized_pnl += pos.unrealized_pnl
            margin_used += abs(pos.qty) * pos.avg_price * self.margin_multiplier

        portfolio.unrealized_pnl = unrealized_pnl
        portfolio.equity = portfolio.cash + unrealized_pnl
        portfolio.margin_used = margin_used
        portfolio.margin_free = portfolio.equity - margin_used

    def _liquidate_positions(
        self,
        portfolio: Portfolio,
        current_candles: Dict[str, Any],
        current_prices: Dict[str, float],
        ts: str,
        all_trades: List[Trade],
        filled_trades_this_step: List[Trade],
    ) -> List[str]:
        """Liquidate all positions on margin call."""
        logs = ["MARGIN CALL: Liquidating all positions!"]

        for sym, pos in list(portfolio.positions.items()):
            close_p = current_prices.get(sym, pos.avg_price)
            liq_dir = "SELL" if pos.qty > 0 else "BUY"
            qty = abs(pos.qty)

            _, _, _, _, _, _, fee = self.execution_sim.calculate_charges(sym, liq_dir, close_p, qty)
            real_p = (close_p - pos.avg_price) * pos.qty
            portfolio.cash += (close_p * pos.qty) - fee
            portfolio.total_pnl += real_p
            portfolio.total_fees += fee

            trade_liq = Trade(
                id=f"T-LIQ-{uuid.uuid4().hex[:6].upper()}",
                order_id="LIQUIDATION",
                timestamp=ts,
                symbol=sym,
                direction=liq_dir,
                price=close_p,
                qty=qty,
                value=close_p * qty,
                total_charges=fee,
            )
            all_trades.append(trade_liq)
            filled_trades_this_step.append(trade_liq)

        portfolio.positions.clear()
        portfolio.margin_used = 0.0
        portfolio.margin_free = portfolio.cash
        portfolio.unrealized_pnl = 0.0
        portfolio.equity = portfolio.cash

        return logs

    def _create_order(
        self,
        order_id: str,
        symbol: str,
        direction: str,
        price: float,
        qty: int,
        ts: str,
    ):
        """Create an Order object."""
        from engine.datamodels import Order as EngineOrder
        return EngineOrder(
            id=order_id,
            symbol=symbol,
            direction=direction,
            type="LIMIT",
            price=price,
            qty=qty,
            status="PENDING",
            trigger_price=None,
            created_at=ts,
        )
