"""
Data adapters: convert between backtester formats and TradingState.

Handles:
1. Candle -> synthetic OrderDepth (best bid/ask from OHLC)
2. DataFrame trade history -> Trade objects
3. Portfolio state -> TradingState
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from engine.runtime.datamodels import (
    OrderDepth, Trade, Position, TradingState, Listing, Observation
)


class CandleToOrderBookAdapter:
    """
    Converts OHLCV candles to synthetic order books.
    
    For each candle, generates a top-of-book OrderDepth:
    - best bid = close - (spread / 2)
    - best ask = close + (spread / 2)
    - size = configurable depth
    
    This allows strategies to run unchanged while internally
    using OrderDepth instead of raw candle rows.
    """

    def __init__(
        self,
        spread_pct: float = 0.01,      # 0.01% = 1 basis point
        depth_size: int = 100,         # default lot size per level
    ):
        """
        Args:
            spread_pct: bid-ask spread as % of close price
            depth_size: volume at each price level
        """
        self.spread_pct = spread_pct
        self.depth_size = depth_size

    def candle_to_order_depth(
        self,
        symbol: str,
        candle_row: pd.Series,
    ) -> OrderDepth:
        """
        Convert a single OHLCV row to OrderDepth.

        Args:
            symbol: instrument symbol
            candle_row: pandas Series with 'open', 'high', 'low', 'close', 'volume'

        Returns:
            OrderDepth with synthetic bid/ask levels
        """
        close = float(candle_row['close'])
        spread = close * (self.spread_pct / 100.0)

        best_bid = close - (spread / 2.0)
        best_ask = close + (spread / 2.0)

        # For now, single level of depth
        # In future, derive from high/low to simulate volume profile
        bid_prices = [int(best_bid * 100) / 100.0]  # 2 decimals
        bid_volumes = [self.depth_size]
        ask_prices = [int(best_ask * 100) / 100.0]
        ask_volumes = [self.depth_size]

        return OrderDepth(
            symbol=symbol,
            bid_prices=bid_prices,
            bid_volumes=bid_volumes,
            ask_prices=ask_prices,
            ask_volumes=ask_volumes,
        )

    def dataframe_to_order_depths(
        self,
        candle_data: Dict[str, pd.DataFrame],
        timestamp: str,
    ) -> Dict[str, OrderDepth]:
        """
        Convert candle data at a specific timestamp to OrderDepths for all symbols.

        Args:
            candle_data: Dict[symbol -> DataFrame with time, open, high, low, close, volume]
            timestamp: target timestamp

        Returns:
            Dict[symbol -> OrderDepth] for this tick
        """
        order_depths = {}

        for symbol, df in candle_data.items():
            # Find row at this timestamp
            mask = df['time'].astype(str) == timestamp
            rows = df[mask]

            if not rows.empty:
                row = rows.iloc[0]
                order_depths[symbol] = self.candle_to_order_depth(symbol, row)

        return order_depths


class PortfolioStateBuilder:
    """
    Constructs TradingState objects from backtester portfolio and execution state.
    
    Bridges the gap between:
    - engine.backtester.py portfolio accounting
    - user strategy's expected TradingState interface
    """

    @staticmethod
    def build_trading_state(
        timestamp: str,
        order_depths: Dict[str, OrderDepth],
        own_trades: Dict[str, List[Trade]],
        market_trades: Dict[str, List[Trade]],
        positions: Dict[str, Position],
        portfolio_equity: float,
        portfolio_cash: float,
        trader_data: str = "{}",
        listings: Optional[Dict[str, Listing]] = None,
        observations: Optional[Dict[str, Observation]] = None,
    ) -> TradingState:
        """
        Build a complete TradingState for a tick.

        Args:
            timestamp: current timestamp (ISO or YYYY-MM-DD HH:MM:SS)
            order_depths: current order books
            own_trades: trades by this strategy, by symbol
            market_trades: all market trades, by symbol
            positions: current positions, by symbol
            portfolio_equity: total account equity
            portfolio_cash: available cash
            trader_data: JSON string (strategy memory from previous ticks)
            listings: optional instrument metadata
            observations: optional custom observations

        Returns:
            TradingState ready for strategy.run(state)
        """
        return TradingState(
            timestamp=timestamp,
            order_depths=order_depths,
            own_trades=own_trades,
            market_trades=market_trades,
            positions=positions,
            portfolio_value=portfolio_equity,
            cash=portfolio_cash,
            trader_data=trader_data,
            listings=listings or {},
            observations=observations or {},
        )

    @staticmethod
    def convert_backtest_positions(
        backtest_positions: Dict[str, Any],
        current_prices: Dict[str, float],
    ) -> Dict[str, Position]:
        """
        Convert backtester position objects to TradingState Position objects.

        Args:
            backtest_positions: from backtester Portfolio.positions
            current_prices: symbol -> current price for unrealized PnL

        Returns:
            Dict[symbol -> Position]
        """
        positions = {}

        for symbol, pos in backtest_positions.items():
            # Assume pos has: qty, avg_price, realized_pnl, unrealized_pnl
            current_price = current_prices.get(symbol, pos.avg_price)
            unrealized = (current_price - pos.avg_price) * pos.qty if pos.qty != 0 else 0.0

            positions[symbol] = Position(
                symbol=symbol,
                quantity=pos.qty,
                avg_price=pos.avg_price,
                realized_pnl=getattr(pos, 'realized_pnl', 0.0),
                unrealized_pnl=unrealized,
            )

        return positions

    @staticmethod
    def convert_trades(
        trades: List[Dict[str, Any]],
    ) -> Dict[str, List[Trade]]:
        """
        Convert backtest trade records to Trade objects, grouped by symbol.

        Args:
            trades: list of trade dicts from backtester

        Returns:
            Dict[symbol -> List[Trade]]
        """
        trade_dict = {}

        for t in trades:
            symbol = t.get('symbol', 'UNKNOWN')
            trade = Trade(
                symbol=symbol,
                price=t.get('price', 0.0),
                quantity=t.get('qty', 0),
                timestamp=t.get('timestamp', ''),
                direction=t.get('direction', 'BUY'),
                trade_id=t.get('id', ''),
            )

            if symbol not in trade_dict:
                trade_dict[symbol] = []
            trade_dict[symbol].append(trade)

        return trade_dict


class ReplayEventBuilder:
    """
    Constructs replay events for frontend consumption.
    
    Merges:
    - backtester events (candles, orders, fills)
    - strategy logs (from Logger.flush())
    - portfolio state snapshots
    """

    @staticmethod
    def build_replay_event(
        step: int,
        timestamp: str,
        trading_state: TradingState,
        orders_submitted: List[Dict[str, Any]],
        orders_filled: List[Dict[str, Any]],
        strategy_logs: str = "",
        portfolio: Any = None,
        current_candles: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Build a single replay event matching the frontend's expected format.

        Frontend expects:
        - candle: { symbol: { open, high, low, close, volume } }
        - orders_submitted: [...]
        - orders_filled: [...]
        - portfolio: { cash, margin_used, margin_free, equity, unrealized_pnl, total_fees, total_pnl, positions }
        - log_messages: ["msg1", "msg2", ...]
        """
        # Parse strategy_logs JSON string into log_messages array
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
            except:
                pass

        # Build candle dict from order_depths (derive from best bid/ask midpoint)
        candle = {}
        if current_candles:
            for sym, row in current_candles.items():
                candle[sym] = {
                    "open": float(row.get("open", row.get("close", 0))),
                    "high": float(row.get("high", row.get("close", 0))),
                    "low": float(row.get("low", row.get("close", 0))),
                    "close": float(row.get("close", 0)),
                    "volume": int(row.get("volume", 0)),
                }
        else:
            # Fallback: derive from order_depths
            for sym, od in trading_state.order_depths.items():
                best_bid = od.bid_prices[0] if od.bid_prices else 0
                best_ask = od.ask_prices[0] if od.ask_prices else 0
                mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
                candle[sym] = {
                    "open": mid,
                    "high": mid,
                    "low": mid,
                    "close": mid,
                    "volume": od.bid_volumes[0] + od.ask_volumes[0] if od.bid_volumes and od.ask_volumes else 0,
                }

        # Build portfolio snapshot
        portfolio_snapshot = {
            "cash": portfolio.cash if portfolio else trading_state.cash,
            "margin_used": getattr(portfolio, "margin_used", 0.0) if portfolio else 0.0,
            "margin_free": getattr(portfolio, "margin_free", 0.0) if portfolio else trading_state.cash,
            "equity": getattr(portfolio, "equity", trading_state.portfolio_value) if portfolio else trading_state.portfolio_value,
            "unrealized_pnl": getattr(portfolio, "unrealized_pnl", 0.0) if portfolio else 0.0,
            "total_fees": getattr(portfolio, "total_fees", 0.0) if portfolio else 0.0,
            "total_pnl": getattr(portfolio, "total_pnl", 0.0) if portfolio else 0.0,
            "positions": {
                sym: {
                    "symbol": sym,
                    "qty": pos.quantity,
                    "avg_price": pos.avg_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                }
                for sym, pos in trading_state.positions.items()
            },
        }

        # Build order_depths snapshot for the frontend order book display
        order_depths_snapshot = {}
        for sym, od in trading_state.order_depths.items():
            order_depths_snapshot[sym] = od.to_dict()

        return {
            "step": step,
            "timestamp": timestamp,
            "candle": candle,
            "order_depths": order_depths_snapshot,
            "orders_submitted": orders_submitted,
            "orders_filled": orders_filled,
            "portfolio": portfolio_snapshot,
            "log_messages": log_messages,
        }
