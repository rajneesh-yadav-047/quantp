"""
Portfolio manager: position tracking, P&L, margin, and liquidation.

Extracted from BacktestEngine to separate portfolio accounting concerns
from backtest orchestration.
"""

import uuid
from typing import Dict, Any, List, Optional
from engine.datamodels import Trade, Position, Portfolio
from engine.execution import ExecutionSimulator


class PortfolioManager:
    """
    Manages portfolio state during a backtest run.
    
    Responsibilities:
    - Track positions with FIFO average price
    - Calculate realized and unrealized P&L
    - Compute margin requirements
    - Detect margin calls and liquidate positions
    """

    def __init__(
        self,
        initial_capital: float,
        default_trade_type: str = "INTRADAY",
        execution_sim: Optional[ExecutionSimulator] = None,
    ):
        self.initial_capital = initial_capital
        self.default_trade_type = default_trade_type
        self.execution_sim = execution_sim or ExecutionSimulator()

        # Margin multiplier based on trade type
        self.margin_multiplier = 0.20  # 5x leverage for INTRADAY
        if default_trade_type == "DELIVERY":
            self.margin_multiplier = 1.0
        elif default_trade_type == "FUTURES":
            self.margin_multiplier = 0.15  # ~6.6x leverage

        self.portfolio = Portfolio(
            cash=initial_capital,
            margin_used=0.0,
            margin_free=initial_capital,
            equity=initial_capital,
            positions={},
            total_fees=0.0,
            total_pnl=0.0,
        )

    def apply_trade(self, trade: Trade) -> None:
        """Update portfolio from a filled trade."""
        pos_sym = trade.symbol
        if pos_sym not in self.portfolio.positions:
            self.portfolio.positions[pos_sym] = Position(symbol=pos_sym)

        pos = self.portfolio.positions[pos_sym]
        direction_multiplier = 1 if trade.direction == "BUY" else -1

        current_qty = pos.qty
        trade_qty = trade.qty

        # Adding to position (same direction)
        if (current_qty >= 0 and direction_multiplier == 1) or (current_qty <= 0 and direction_multiplier == -1):
            total_cost = (pos.qty * pos.avg_price) + (trade.price * trade.qty * direction_multiplier)
            pos.qty += trade.qty * direction_multiplier
            if pos.qty != 0:
                pos.avg_price = abs(total_cost / pos.qty)
        else:
            # Closing or reducing (opposite direction)
            matched_qty = min(abs(current_qty), trade_qty)
            pnl = (trade.price - pos.avg_price) * matched_qty * (1 if current_qty > 0 else -1)
            pos.realized_pnl += pnl
            self.portfolio.total_pnl += pnl

            pos.qty += trade.qty * direction_multiplier
            remaining_qty = trade_qty - matched_qty
            if remaining_qty > 0 and pos.qty != 0:
                pos.avg_price = trade.price

        # Update cash for trade value + charges
        trade_value = trade.price * trade.qty
        if trade.direction == "BUY":
            self.portfolio.cash -= trade_value
        else:
            self.portfolio.cash += trade_value
        self.portfolio.cash -= trade.total_charges
        self.portfolio.total_fees += trade.total_charges

        # Clean up zero positions
        if pos.qty == 0:
            pos.avg_price = 0.0
            pos.unrealized_pnl = 0.0

    def mark_to_market(self, current_prices: Dict[str, float]) -> None:
        """Mark positions to market and update unrealized P&L."""
        unrealized_pnl = 0.0
        position_value = 0.0
        margin_used = 0.0

        for sym, pos in self.portfolio.positions.items():
            close_price = current_prices.get(sym, pos.avg_price)
            pos.unrealized_pnl = (close_price - pos.avg_price) * pos.qty
            unrealized_pnl += pos.unrealized_pnl
            position_value += pos.qty * close_price
            margin_used += abs(pos.qty) * pos.avg_price * self.margin_multiplier

        self.portfolio.unrealized_pnl = unrealized_pnl
        self.portfolio.equity = self.portfolio.cash + position_value
        self.portfolio.margin_used = margin_used
        self.portfolio.margin_free = self.portfolio.equity - margin_used

    def is_margin_call(self) -> bool:
        """Check if portfolio has hit a margin call."""
        return self.portfolio.equity <= 0 or self.portfolio.margin_free < 0

    def liquidate_all(
        self,
        current_prices: Dict[str, float],
        timestamp: str,
        execution_sim: Optional[ExecutionSimulator] = None,
    ) -> List[Trade]:
        """
        Liquidate all positions on margin call.
        
        Returns:
            List of liquidation trades
        """
        sim = execution_sim or self.execution_sim
        liquidation_trades: List[Trade] = []

        for sym, pos in list(self.portfolio.positions.items()):
            close_p = current_prices.get(sym, pos.avg_price)
            liq_dir = "SELL" if pos.qty > 0 else "BUY"
            qty = abs(pos.qty)

            _, _, _, _, _, _, fee = sim.calculate_charges(sym, liq_dir, close_p, qty)
            real_p = (close_p - pos.avg_price) * pos.qty
            self.portfolio.cash += (close_p * pos.qty) - fee
            self.portfolio.total_pnl += real_p
            self.portfolio.total_fees += fee

            trade_liq = Trade(
                id=f"T-LIQ-{uuid.uuid4().hex[:6].upper()}",
                order_id="LIQUIDATION",
                timestamp=timestamp,
                symbol=sym,
                direction=liq_dir,
                price=close_p,
                qty=qty,
                value=close_p * qty,
                total_charges=fee,
            )
            liquidation_trades.append(trade_liq)

        self.portfolio.positions.clear()
        self.portfolio.margin_used = 0.0
        self.portfolio.margin_free = self.portfolio.cash
        self.portfolio.unrealized_pnl = 0.0
        self.portfolio.equity = self.portfolio.cash

        return liquidation_trades

    def get_snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serializable portfolio snapshot."""
        return {
            "cash": self.portfolio.cash,
            "margin_used": self.portfolio.margin_used,
            "margin_free": self.portfolio.margin_free,
            "equity": self.portfolio.equity,
            "unrealized_pnl": self.portfolio.unrealized_pnl,
            "total_fees": self.portfolio.total_fees,
            "total_pnl": self.portfolio.total_pnl,
            "positions": {
                sym: {
                    "symbol": sym,
                    "qty": pos.qty,
                    "avg_price": pos.avg_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for sym, pos in self.portfolio.positions.items()
            },
        }
