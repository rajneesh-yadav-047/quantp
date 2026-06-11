"""
Order manager: order lifecycle, matching, and position sizing.

Extracted from BacktestEngine to separate order execution concerns
from backtest orchestration.
"""

import uuid
from typing import List, Dict, Any, Optional
from engine.datamodels import Order, Trade
from engine.execution import ExecutionSimulator
from engine.runtime.datamodels import Trade as RTrade


class OrderManager:
    """
    Manages order lifecycle during a backtest run.
    
    Responsibilities:
    - Queue pending LIMIT orders
    - Execute MARKET orders immediately
    - Match pending orders against current candles
    - Enforce max position size caps
    - Track active and filled orders
    """

    def __init__(
        self,
        execution_sim: ExecutionSimulator,
        max_position_size: Optional[int] = None,
    ):
        self.execution_sim = execution_sim
        self.max_position_size = max_position_size
        self.active_orders: List[Order] = []

    def match_pending_orders(
        self,
        current_candles: Dict[str, Any],
        timestamp: str,
        current_positions: Dict[str, Any],
    ) -> tuple[List[Trade], List[RTrade]]:
        """
        Try to fill pending orders against current candles.
        
        Args:
            current_candles: symbol -> candle row
            timestamp: current timestamp
            current_positions: symbol -> Position (for sizing, not modified here)
            
        Returns:
            (filled_trades, rtrades_for_state)
        """
        filled_trades: List[Trade] = []
        rtrades: List[RTrade] = []
        remaining_orders: List[Order] = []

        for order in self.active_orders:
            if order.symbol in current_candles:
                trade = self.execution_sim.match_order(order, current_candles[order.symbol], timestamp)
                if trade:
                    filled_trades.append(trade)
                    rtrades.append(RTrade(
                        symbol=trade.symbol,
                        price=trade.price,
                        quantity=trade.qty,
                        timestamp=timestamp,
                        direction=trade.direction,
                        trade_id=trade.id,
                    ))
                else:
                    remaining_orders.append(order)
            else:
                remaining_orders.append(order)

        self.active_orders = remaining_orders
        return filled_trades, rtrades

    def process_submitted_orders(
        self,
        submitted_orders: List[Any],
        current_candles: Dict[str, Any],
        timestamp: str,
        current_positions: Dict[str, Any],
    ) -> tuple[List[Order], List[Trade], List[RTrade]]:
        """
        Process orders returned by strategy, applying position sizing and execution.
        
        Args:
            submitted_orders: orders from strategy runtime
            current_candles: symbol -> candle row
            timestamp: current timestamp
            current_positions: symbol -> Position (for sizing checks)
            
        Returns:
            (new_orders_list, filled_trades, rtrades_for_state)
        """
        new_orders: List[Order] = []
        filled_trades: List[Trade] = []
        rtrades: List[RTrade] = []

        for order_req in submitted_orders:
            # Normalize to Order object if dict
            order_dict = self._normalize_order_request(order_req)
            if not order_dict:
                continue

            symbol = order_dict["symbol"]
            current_pos_qty = current_positions.get(symbol, type("Pos", (), {"qty": 0})()).qty

            # Determine signed order quantity
            direction_multiplier = 1 if order_dict["direction"] == "BUY" else -1
            requested_signed_qty = order_dict["quantity"] * direction_multiplier

            # Apply max_position_size cap on TOTAL projected position
            final_signed_qty = requested_signed_qty
            if self.max_position_size and self.max_position_size > 0:
                projected_pos = current_pos_qty + requested_signed_qty
                if abs(projected_pos) > self.max_position_size:
                    allowed_new_pos = self.max_position_size if projected_pos >= 0 else -self.max_position_size
                    final_signed_qty = allowed_new_pos - current_pos_qty
                    if final_signed_qty == 0:
                        continue

            final_qty = abs(final_signed_qty)
            final_direction = "BUY" if final_signed_qty > 0 else "SELL"

            order_id = f"O-{uuid.uuid4().hex[:8].upper()}"
            new_order = Order(
                id=order_id,
                symbol=symbol,
                direction=final_direction,
                type=order_dict["type"],
                price=order_dict["price"],
                qty=final_qty,
                status="PENDING",
                trigger_price=0.0,
                created_at=timestamp,
            )

            # MARKET orders execute immediately
            if order_dict["type"] == "MARKET" and symbol in current_candles:
                trade = self.execution_sim.match_order(new_order, current_candles[symbol], timestamp)
                if trade:
                    filled_trades.append(trade)
                    rtrades.append(RTrade(
                        symbol=trade.symbol,
                        price=trade.price,
                        quantity=trade.qty,
                        timestamp=timestamp,
                        direction=trade.direction,
                        trade_id=trade.id,
                    ))
            else:
                # LIMIT orders queue for future matching
                self.active_orders.append(new_order)

            new_orders.append(new_order)

        return new_orders, filled_trades, rtrades

    @staticmethod
    def _normalize_order_request(order_req: Any) -> Optional[Dict[str, Any]]:
        """Normalize various order formats to a standard dict."""
        if hasattr(order_req, "symbol"):
            # It's an Order object (from runtime)
            return {
                "symbol": order_req.symbol,
                "direction": getattr(order_req, "direction", "BUY"),
                "type": getattr(order_req, "type", "LIMIT"),
                "price": getattr(order_req, "price", 0.0),
                "quantity": getattr(order_req, "quantity", getattr(order_req, "qty", 0)),
            }
        elif isinstance(order_req, dict):
            d = dict(order_req)
            if "qty" in d and "quantity" not in d:
                d["quantity"] = d.pop("qty")
            if "symbol" not in d or "direction" not in d:
                return None
            return {
                "symbol": d["symbol"],
                "direction": d.get("direction", "BUY"),
                "type": d.get("type", "LIMIT"),
                "price": d.get("price", 0.0),
                "quantity": d.get("quantity", 0),
            }
        return None

    def prune_zero_positions(self, positions: Dict[str, Any]) -> Dict[str, Any]:
        """Remove zero-quantity positions from dict."""
        return {k: v for k, v in positions.items() if getattr(v, "qty", 0) != 0}
