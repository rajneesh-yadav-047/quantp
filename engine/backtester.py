"""
Event-driven backtesting engine with Prosperity runtime integration.

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
from typing import List, Dict, Any, Optional
import pandas as pd

from engine.datamodels import Candle, MarketState
from engine.execution import ExecutionSimulator
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
    ):
        self.df_dict = df_dict
        self.strategy_code = strategy_code
        self.initial_capital = initial_capital
        self.log_dir = log_dir
        self.runtime_type = runtime_type

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

        os.makedirs(self.log_dir, exist_ok=True)

        # Historical candles for legacy on_bar strategies
        self.historical_candles: Dict[str, List[Candle]] = {sym: [] for sym in df_dict.keys()}

        self._normalize_time_columns()
        self.all_timestamps = self._align_timestamps()

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
                new_orders, new_filled, new_rtrades = self.order_mgr.process_submitted_orders(
                    submitted_orders=submitted_orders,
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

                # ===== PHASE 7: Finalize =====
                self.portfolio_mgr.mark_to_market(current_prices)
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
                    "position_count": len(self.portfolio_mgr.portfolio.positions),
                    "total_qty": sum(abs(p.qty) for p in self.portfolio_mgr.portfolio.positions.values()),
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
                    portfolio_snapshot=self.portfolio_mgr.get_snapshot(),
                    current_candles=current_candles,
                )
                logger.write_event(replay_event)

        return {
            "run_id": run_id,
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
                }
                for t in all_trades
            ],
            "equity_curve": equity_curve,
            "final_portfolio": {
                "equity": self.portfolio_mgr.portfolio.equity,
                "cash": self.portfolio_mgr.portfolio.cash,
                "total_pnl": self.portfolio_mgr.portfolio.total_pnl,
                "total_fees": self.portfolio_mgr.portfolio.total_fees,
                "positions": len(self.portfolio_mgr.portfolio.positions),
            },
            "log_file_path": log_file_path,
        }
