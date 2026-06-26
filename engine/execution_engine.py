"""
ExecutionEngine: Consolidated order placement, matching, and execution simulation.

Leverages the existing OrderManager and ExecutionSimulator while producing standardized
trade events. This is the single source of truth for all order execution logic.

Responsibilities:
- Match pending orders against current market data
- Process new orders submitted by strategies (MARKET immediate fill, LIMIT queue)
- Apply position sizing constraints (max_position_size)
- Calculate trade charges using ExecutionSimulator
- Produce standardized TradeEvent objects for consumers
- Interface with PortfolioManager for trade application

No strategy logic. No market data fetching. No persistence. No event broadcasting directly.
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

from engine.execution import ExecutionSimulator
from engine.order_manager import OrderManager
from engine.portfolio import PortfolioManager
from engine.datamodels import Order, Trade, Candle
from engine.runtime.datamodels import Trade as RTrade


@dataclass
class TradeEvent:
    """Standardized trade execution event."""
    trade_id: str
    order_id: str
    symbol: str
    direction: str
    price: float
    qty: int
    value: float
    total_charges: float
    timestamp: str
    trade_type: str = "INTRADAY"
    charges_source: str = "calculated"
    # Charge breakdown
    brokerage: float = 0.0
    stt: float = 0.0
    exc_charges: float = 0.0
    gst: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0


@dataclass
class OrderEvent:
    """Standardized order event."""
    order_id: str
    symbol: str
    direction: str
    order_type: str
    price: float
    qty: int
    status: str
    timestamp: str


class ExecutionEngine:
    """
    Centralized execution engine for order processing and trade simulation.
    
    Owns OrderManager and ExecutionSimulator instances.
    Coordinates with PortfolioManager for trade application.
    """
    
    def __init__(
        self,
        portfolio_mgr: PortfolioManager,
        execution_sim: Optional[ExecutionSimulator] = None,
        max_position_size: Optional[int] = None,
        slippage_pct: float = 0.0,
        trade_type: str = "INTRADAY",
    ):
        self.portfolio_mgr = portfolio_mgr
        self.execution_sim = execution_sim or ExecutionSimulator(
            slippage_pct=slippage_pct,
            default_trade_type=trade_type
        )
        self.order_mgr = OrderManager(
            execution_sim=self.execution_sim,
            max_position_size=max_position_size,
        )
        self.trade_type = trade_type
    
    def match_pending_orders(
        self,
        current_candles: Dict[str, Any],
        timestamp: str,
    ) -> Tuple[List[TradeEvent], List[RTrade]]:
        """
        Match pending LIMIT orders against current market data.
        
        Args:
            current_candles: symbol -> candle dict
            timestamp: current tick timestamp
            
        Returns:
            (filled_trade_events, rtrades_for_state)
        """
        filled_trades, rtrades = self.order_mgr.match_pending_orders(
            current_candles=current_candles,
            timestamp=timestamp,
            current_positions=self.portfolio_mgr.portfolio.positions,
        )
        
        trade_events = []
        for trade in filled_trades:
            self.portfolio_mgr.apply_trade(trade)
            trade_events.append(self._to_trade_event(trade))
        
        # Prune zero positions
        self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
            self.portfolio_mgr.portfolio.positions
        )
        
        return trade_events, rtrades
    
    def process_new_orders(
        self,
        submitted_orders: List[Any],
        current_candles: Dict[str, Any],
        timestamp: str,
    ) -> Tuple[List[OrderEvent], List[TradeEvent], List[RTrade]]:
        """
        Process orders submitted by the strategy.
        
        Args:
            submitted_orders: orders from strategy runtime
            current_candles: symbol -> candle dict
            timestamp: current tick timestamp
            
        Returns:
            (order_events, filled_trade_events, rtrades_for_state)
        """
        new_orders, new_filled, new_rtrades = self.order_mgr.process_submitted_orders(
            submitted_orders=submitted_orders,
            current_candles=current_candles,
            timestamp=timestamp,
            current_positions=self.portfolio_mgr.portfolio.positions,
        )
        
        order_events = []
        for order in new_orders:
            order_events.append(OrderEvent(
                order_id=order.id,
                symbol=order.symbol,
                direction=order.direction,
                order_type=order.type,
                price=order.price,
                qty=order.qty,
                status=order.status,
                timestamp=timestamp,
            ))
        
        trade_events = []
        for trade in new_filled:
            self.portfolio_mgr.apply_trade(trade)
            trade_events.append(self._to_trade_event(trade))
        
        # Prune zero positions
        self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
            self.portfolio_mgr.portfolio.positions
        )
        
        return order_events, trade_events, new_rtrades
    
    def execute_manual_order(
        self,
        symbol: str,
        direction: str,
        qty: int,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        current_price: Optional[float] = None,
        timestamp: Optional[str] = None,
        use_real_charges: bool = True,
        smartapi_client: Optional[Any] = None,
    ) -> TradeEvent:
        """
        Execute a manual order (bypasses normal order lifecycle for immediate fill).
        
        Args:
            symbol: trading symbol
            direction: BUY or SELL
            qty: quantity
            price: limit price (for LIMIT orders)
            order_type: MARKET or LIMIT
            current_price: current market price (for MARKET orders)
            timestamp: trade timestamp
            use_real_charges: whether to use SmartAPI charges API
            smartapi_client: optional SmartAPI client for real charges
            
        Returns:
            TradeEvent for the filled trade
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        execution_price = price if (order_type.upper() == "LIMIT" and price is not None) else current_price
        if execution_price is None:
            raise ValueError("Current price required for MARKET manual orders")
        
        # Calculate charges
        charges_source = "calculated"
        charges = self._calculate_charges(
            symbol, direction, execution_price, qty,
            use_real_charges, smartapi_client
        )
        
        trade = Trade(
            id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            timestamp=timestamp,
            symbol=symbol,
            direction=direction.upper(),
            price=execution_price,
            qty=qty,
            value=execution_price * qty,
            slippage=0.0,
            brokerage=charges.get("brokerage", 0.0),
            stt=charges.get("stt", 0.0),
            exc_charges=charges.get("exc_charges", 0.0),
            gst=charges.get("gst", 0.0),
            sebi_charges=charges.get("sebi_charges", 0.0),
            stamp_duty=charges.get("stamp_duty", 0.0),
            total_charges=charges.get("total_charges", 0.0),
        )
        
        self.portfolio_mgr.apply_trade(trade)
        self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
            self.portfolio_mgr.portfolio.positions
        )
        
        return self._to_trade_event(trade, charges_source=charges_source)
    
    def check_margin_and_liquidate(
        self,
        current_prices: Dict[str, float],
        timestamp: str,
    ) -> List[TradeEvent]:
        """
        Check for margin calls and liquidate if necessary.
        
        Returns:
            List of liquidation trade events (empty if no margin call)
        """
        if not self.portfolio_mgr.is_margin_call():
            return []
        
        liq_trades = self.portfolio_mgr.liquidate_all(
            current_prices=current_prices,
            timestamp=timestamp,
            execution_sim=self.execution_sim,
        )
        
        trade_events = []
        for trade in liq_trades:
            trade_events.append(self._to_trade_event(trade))
        
        return trade_events
    
    def liquidate_all_positions(
        self,
        current_prices: Dict[str, float],
        timestamp: str,
    ) -> List[TradeEvent]:
        """
        Liquidate all open positions in the portfolio immediately.
        
        Returns:
            List of liquidation trade events
        """
        liq_trades = self.portfolio_mgr.liquidate_all(
            current_prices=current_prices,
            timestamp=timestamp,
            execution_sim=self.execution_sim,
        )
        
        trade_events = []
        for trade in liq_trades:
            trade_events.append(self._to_trade_event(trade))
            
        return trade_events
    
    def mark_to_market(self, current_prices: Dict[str, float]):
        """Mark portfolio to market using current prices."""
        self.portfolio_mgr.mark_to_market(current_prices)
    
    def get_active_orders(self) -> List[Order]:
        """Get currently active (pending) orders."""
        return self.order_mgr.active_orders
    
    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        """Get the current portfolio snapshot."""
        return self.portfolio_mgr.get_snapshot()
    
    def _to_trade_event(self, trade: Trade, charges_source: str = "calculated") -> TradeEvent:
        """Convert a Trade object to a standardized TradeEvent."""
        return TradeEvent(
            trade_id=trade.id,
            order_id=trade.order_id,
            symbol=trade.symbol,
            direction=trade.direction,
            price=trade.price,
            qty=trade.qty,
            value=trade.value,
            total_charges=trade.total_charges,
            timestamp=trade.timestamp,
            trade_type=self.trade_type,
            charges_source=charges_source,
            brokerage=getattr(trade, 'brokerage', 0.0),
            stt=getattr(trade, 'stt', 0.0),
            exc_charges=getattr(trade, 'exc_charges', 0.0),
            gst=getattr(trade, 'gst', 0.0),
            sebi_charges=getattr(trade, 'sebi_charges', 0.0),
            stamp_duty=getattr(trade, 'stamp_duty', 0.0),
        )
    
    def _calculate_charges(
        self,
        symbol: str,
        direction: str,
        price: float,
        qty: int,
        use_real_charges: bool,
        smartapi_client: Optional[Any],
    ) -> Dict[str, float]:
        """Calculate charges for a trade, optionally using SmartAPI API."""
        # Base calculation from ExecutionSimulator
        brokerage, stt, exc, gst, sebi, stamp, total = self.execution_sim.calculate_charges(
            symbol=symbol,
            direction=direction,
            price=price,
            qty=qty,
            trade_type=self.trade_type,
        )
        charges = {
            "brokerage": brokerage, "stt": stt, "exc_charges": exc,
            "gst": gst, "sebi_charges": sebi, "stamp_duty": stamp, "total_charges": total,
        }
        
        # Try SmartAPI for real charges if configured
        if use_real_charges and smartapi_client:
            try:
                api_charges = smartapi_client.calculate_charges_api(
                    symbol=symbol,
                    direction=direction,
                    price=price,
                    qty=qty,
                    trade_type=self.trade_type,
                )
                if api_charges and isinstance(api_charges, dict):
                    # Normalize API response keys to our standard keys
                    key_map = {
                        "exchange_charges": "exc_charges",
                        "exc_charges": "exc_charges",
                    }
                    for api_key, our_key in key_map.items():
                        if api_key in api_charges and our_key not in api_charges:
                            api_charges[our_key] = api_charges[api_key]
                    # Only override keys that exist in our format
                    for key in charges:
                        if key in api_charges:
                            charges[key] = api_charges[key]
            except Exception:
                pass
        
        return charges
