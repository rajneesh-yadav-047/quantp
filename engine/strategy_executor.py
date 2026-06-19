"""
StrategyExecutor: Isolated strategy execution module.

Responsible ONLY for converting market state into trading decisions through the existing
runtime infrastructure (RuntimeFactory, ProsperityRuntime, LegacyRuntime).

No order management. No portfolio logic. No persistence. No market data fetching.
Pure strategy execution: receives market state, produces orders.
"""

import json
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from engine.datamodels import Candle, MarketState
from engine.runtime.runtimes import RuntimeFactory, LegacyRuntime
from engine.runtime.adapters import CandleToOrderBookAdapter, PortfolioStateBuilder
from engine.runtime.datamodels import TradingState


class StrategyExecutor:
    """
    Executes strategy code for a single deployment.
    
    Responsibilities:
    - Maintain strategy runtime instance (RuntimeFactory)
    - Build TradingState/MarketState from market data and portfolio snapshot
    - Execute strategy on_tick/on_bar
    - Return submitted orders and strategy logs
    - Track trader_data state between ticks
    """
    
    def __init__(
        self,
        strategy_code: str,
        runtime_type: str = "legacy_on_bar",
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.strategy_code = strategy_code
        self.runtime_type = runtime_type
        self.parameters = parameters or {}
        self.runtime = RuntimeFactory.create_runtime(
            strategy_code=strategy_code,
            runtime_type=runtime_type,
            parameters=self.parameters,
        )
        self.trader_data_json = "{}"
        self.own_trades: List[Any] = []  # RTrade instances for state building
        self.order_book_adapter = CandleToOrderBookAdapter(spread_pct=0.01, depth_size=100)
    
    def execute(
        self,
        timestamp: str,
        candle: Candle,
        candle_data: Dict[str, Any],
        historical_candles: List[Candle],
        current_prices: Dict[str, float],
        portfolio_positions: Dict[str, Any],
        portfolio_equity: float,
        portfolio_cash: float,
        active_orders: List[Any],
        portfolio: Any,  # Portfolio object from PortfolioManager
    ) -> Tuple[List[Any], str, List[str]]:
        """
        Execute the strategy for one tick.
        
        Args:
            timestamp: current tick timestamp
            candle: current Candle object
            candle_data: raw candle dict for order book adapter
            historical_candles: list of previous Candle objects
            current_prices: symbol -> current LTP
            portfolio_positions: symbol -> Position objects
            portfolio_equity: total equity
            portfolio_cash: available cash
            active_orders: list of pending Order objects
            portfolio: Portfolio object for MarketState
            
        Returns:
            (submitted_orders, trader_data_json, strategy_logs)
        """
        # Build order depth from candle
        order_depth = self.order_book_adapter.candle_to_order_depth(
            candle.symbol if hasattr(candle, 'symbol') else list(current_prices.keys())[0],
            pd.Series(candle_data)
        )
        
        # Convert positions to TradingState format
        positions_for_state = PortfolioStateBuilder.convert_backtest_positions(
            portfolio_positions,
            current_prices
        )
        
        # Build TradingState
        symbol = list(current_prices.keys())[0] if current_prices else ""
        trading_state = PortfolioStateBuilder.build_trading_state(
            timestamp=timestamp,
            order_depths={symbol: order_depth} if symbol else {},
            own_trades={symbol: self.own_trades[-100:]} if symbol else {},
            market_trades={symbol: []} if symbol else {},
            positions=positions_for_state,
            portfolio_equity=portfolio_equity,
            portfolio_cash=portfolio_cash,
            trader_data=self.trader_data_json,
        )
        
        submitted_orders = []
        
        if portfolio_equity > 0:
            if isinstance(self.runtime, LegacyRuntime):
                market_state = MarketState(
                    current_time=timestamp,
                    current_candle={symbol: candle} if symbol else {},
                    historical_candles={symbol: list(historical_candles)} if symbol else {},
                    positions=portfolio_positions,
                    portfolio=portfolio,
                    active_orders=active_orders,
                )
                submitted_orders, self.trader_data_json = self.runtime.on_tick(market_state)
            else:
                submitted_orders, self.trader_data_json = self.runtime.on_tick(trading_state)
        
        strategy_logs = self.runtime.get_logs()
        # Parse logs into list of strings
        log_messages = []
        if strategy_logs:
            try:
                logs = json.loads(strategy_logs)
                if isinstance(logs, list):
                    for entry in logs:
                        if isinstance(entry, dict):
                            msg = entry.get("message", "")
                            if msg:
                                log_messages.append(msg)
                        elif isinstance(entry, str):
                            log_messages.append(entry)
            except Exception:
                pass
        
        return submitted_orders, self.trader_data_json, log_messages
    
    def record_own_trade(self, trade: Any):
        """Record a trade for inclusion in the next TradingState."""
        self.own_trades.append(trade)
        # Keep only last 100 trades
        if len(self.own_trades) > 100:
            self.own_trades = self.own_trades[-100:]
    
    def get_logs(self) -> List[str]:
        """Get the latest strategy logs."""
        return self.runtime.get_logs()
    
    def reset(self):
        """Reset the executor state (for new deployments or resets)."""
        self.trader_data_json = "{}"
        self.own_trades = []
        self.runtime = RuntimeFactory.create_runtime(
            strategy_code=self.strategy_code,
            runtime_type=self.runtime_type,
            parameters=self.parameters,
        )
