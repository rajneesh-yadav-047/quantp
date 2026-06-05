import uuid
from typing import List, Tuple, Optional
from datetime import datetime
from engine.datamodels import Order, Trade, Candle

class ExecutionSimulator:
    def __init__(
        self,
        slippage_pct: float = 0.0005,  # 0.05% default slippage
        latency_ms: int = 0,
        default_trade_type: str = "INTRADAY"  # INTRADAY or DELIVERY or FUTURES
    ):
        self.slippage_pct = slippage_pct
        self.latency_ms = latency_ms
        self.default_trade_type = default_trade_type

    def determine_trade_type(self, symbol: str) -> str:
        """Helper to classify symbol into Equities or F&O."""
        symbol_upper = symbol.upper()
        if symbol_upper.endswith("-FUT") or symbol_upper.endswith("-CE") or symbol_upper.endswith("-PE") or "FUT" in symbol_upper:
            return "FUTURES"
        # If it contains -DEL or user configured, delivery.
        if "DELIVERY" in self.default_trade_type.upper():
            return "DELIVERY"
        return "INTRADAY"

    def calculate_charges(
        self,
        symbol: str,
        direction: str,  # BUY or SELL
        price: float,
        qty: int,
        trade_type: Optional[str] = None
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculates Indian market charges.
        Returns:
            (brokerage, stt, exchange_charges, gst, sebi_charges, stamp_duty, total_charges)
        """
        direction = direction.upper()
        if not trade_type:
            trade_type = self.determine_trade_type(symbol)
        
        turnover = price * qty
        brokerage = 0.0
        stt = 0.0
        exchange_charges = 0.0
        gst = 0.0
        sebi_charges = 0.0
        stamp_duty = 0.0

        # 1. Brokerage: Flat Rs 20 or 0.03% (whichever is lower) for Intraday and Futures. Free for Delivery.
        if trade_type == "DELIVERY":
            brokerage = 0.0
        elif trade_type in ("INTRADAY", "FUTURES"):
            calc_brokerage = turnover * 0.0003  # 0.03%
            brokerage = min(20.0, calc_brokerage)

        # 2. STT (Securities Transaction Tax) / CTT
        if trade_type == "DELIVERY":
            stt = turnover * 0.001  # 0.1% on buy and sell
        elif trade_type == "INTRADAY":
            if direction == "SELL":
                stt = turnover * 0.00025  # 0.025% on sell only
        elif trade_type == "FUTURES":
            if direction == "SELL":
                stt = turnover * 0.000125  # 0.0125% on sell only

        # 3. Exchange Transaction Charges (NSE standard)
        if trade_type == "FUTURES":
            exchange_charges = turnover * 0.000019  # 0.0019%
        else:
            exchange_charges = turnover * 0.0000343  # 0.00343% for equities

        # 4. GST: 18% on (Brokerage + Exchange Charges)
        gst = (brokerage + exchange_charges) * 0.18

        # 5. SEBI Charges: Rs 10 per crore (0.0001%)
        sebi_charges = turnover * 0.0000001

        # 6. Stamp Duty: Buy-side only
        if direction == "BUY":
            if trade_type == "DELIVERY":
                stamp_duty = turnover * 0.00015  # 0.015%
            elif trade_type == "INTRADAY":
                stamp_duty = turnover * 0.00003  # 0.003%
            elif trade_type == "FUTURES":
                stamp_duty = turnover * 0.00002  # 0.002%

        total_charges = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
        return brokerage, stt, exchange_charges, gst, sebi_charges, stamp_duty, total_charges

    def match_order(self, order: Order, candle: Candle, timestamp: str) -> Optional[Trade]:
        """
        Attempts to match an order against a candle.
        Returns a Trade object if filled, otherwise None.
        """
        if order.status != "PENDING":
            return None

        is_filled = False
        fill_price = 0.0
        slippage_value = 0.0

        # slippage calculation: BUY price goes up, SELL price goes down.
        sign = 1 if order.direction == "BUY" else -1

        if order.type == "MARKET":
            # Market orders fill at the candle's open price
            fill_price = candle.open
            slippage_value = fill_price * self.slippage_pct * sign
            fill_price += slippage_value
            is_filled = True

        elif order.type == "LIMIT":
            # For Limit Buy, price must be high enough to match low (candle low <= order price)
            if order.direction == "BUY":
                if candle.low <= order.price:
                    fill_price = order.price  # Limit orders fill at limit price or better
                    slippage_value = fill_price * self.slippage_pct
                    # Limit buys get filled at limit price + slippage (pessimistic modeling)
                    fill_price += slippage_value
                    is_filled = True
            # For Limit Sell, price must be low enough to match high (candle high >= order price)
            elif order.direction == "SELL":
                if candle.high >= order.price:
                    fill_price = order.price
                    slippage_value = -fill_price * self.slippage_pct
                    fill_price += slippage_value
                    is_filled = True

        if is_filled:
            order.status = "FILLED"
            order.filled_at = timestamp
            order.filled_qty = order.qty
            order.avg_fill_price = fill_price

            # Calculate charges
            trade_type = self.determine_trade_type(order.symbol)
            brokerage, stt, exc, gst, sebi, stamp, total = self.calculate_charges(
                order.symbol, order.direction, fill_price, order.qty, trade_type
            )

            return Trade(
                id=f"T-{uuid.uuid4().hex[:8].upper()}",
                order_id=order.id,
                timestamp=timestamp,
                symbol=order.symbol,
                direction=order.direction,
                price=fill_price,
                qty=order.qty,
                value=fill_price * order.qty,
                slippage=abs(slippage_value) * order.qty,
                brokerage=brokerage,
                stt=stt,
                exc_charges=exc,
                gst=gst,
                sebi_charges=sebi,
                stamp_duty=stamp,
                total_charges=total
            )

        return None
