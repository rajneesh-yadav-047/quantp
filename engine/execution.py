import uuid
from typing import List, Tuple, Optional, Any
from datetime import datetime
from engine.datamodels import Order, Trade, Candle


def calculate_options_charges(
    transaction_type: str,
    premium: float,
    strike: float,
    lot_size: int,
    quantity_lots: int,
    is_expiry_day: bool,
    is_itm: bool,
) -> dict:
    """
    Compute options-specific charges for Indian NSE F&O equity/index options.

    Args:
        transaction_type: "BUY" or "SELL".
        premium: Option premium per unit.
        strike: Strike price of the option.
        lot_size: Lot size of the contract.
        quantity_lots: Number of lots traded.
        is_expiry_day: True if the trade happens on expiry day.
        is_itm: True if the option is In-The-Money (used for expiry-day auto-exercise STT).

    Returns:
        Dict with each charge broken out and a total_charges key.
    """
    turnover = premium * lot_size * quantity_lots

    brokerage = min(20.0, 0.0003 * turnover)

    stt = 0.0
    if transaction_type.upper() == "SELL":
        stt = 0.0005 * turnover

    exchange_charges = 0.000053 * turnover
    gst = 0.18 * (brokerage + exchange_charges)
    sebi_charges = 0.000001 * turnover

    stamp_duty = 0.0
    if transaction_type.upper() == "BUY":
        stamp_duty = 0.00003 * turnover

    expiry_stt = 0.0
    if is_expiry_day and is_itm:
        expiry_stt = 0.00125 * strike * lot_size * quantity_lots

    total_charges = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty + expiry_stt

    return {
        "brokerage": brokerage,
        "stt": stt,
        "exchange_charges": exchange_charges,
        "gst": gst,
        "sebi_charges": sebi_charges,
        "stamp_duty": stamp_duty,
        "expiry_stt": expiry_stt,
        "total_charges": total_charges,
    }


class ExecutionSimulator:
    def __init__(
        self,
        slippage_pct: float = 0.0005,  # 0.05% default slippage
        latency_ms: int = 0,
        default_trade_type: str = "INTRADAY"  # INTRADAY, DELIVERY, FUTURES, or OPTIONS
    ):
        self.slippage_pct = slippage_pct
        self.latency_ms = latency_ms
        self.default_trade_type = default_trade_type

    def calculate_charges(
        self,
        symbol: str,
        direction: str,  # BUY or SELL
        price: float,
        qty: int,
        trade_type: Optional[str] = None,
        instrument_type: Optional[str] = None,
        strike: float = 0.0,
        lot_size: int = 0,
        is_expiry_day: bool = False,
        is_itm: bool = False,
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculates Indian market charges (NSE/BSE).
        
        Supports options charge calculation via instrument_type="OPTION".
        When instrument_type is OPTION, delegates to calculate_options_charges
        so the existing equity charge path remains completely untouched.
        
        Returns:
            (brokerage, stt, exchange_charges, gst, sebi_charges, stamp_duty, total_charges)
        """
        # New branch: options charges via dedicated options calculator
        if (instrument_type and instrument_type.upper() == "OPTION") or (trade_type and trade_type.upper() == "OPTIONS"):
            if lot_size == 0:
                lot_size = qty  # fallback if lot_size not provided
            quantity_lots = max(1, qty // lot_size) if lot_size > 0 else 1
            charges = calculate_options_charges(
                transaction_type=direction,
                premium=price,
                strike=strike,
                lot_size=lot_size,
                quantity_lots=quantity_lots,
                is_expiry_day=is_expiry_day,
                is_itm=is_itm,
            )
            return (
                charges["brokerage"],
                charges["stt"],
                charges["exchange_charges"],
                charges["gst"],
                charges["sebi_charges"],
                charges["stamp_duty"],
                charges["total_charges"],
            )

        direction = direction.upper()
        if not trade_type:
            trade_type = self.default_trade_type
        
        turnover = price * qty
        brokerage = 0.0
        stt = 0.0
        exchange_charges = 0.0
        gst = 0.0
        sebi_charges = 0.0
        stamp_duty = 0.0

        # 1. Brokerage: Flat Rs 20 or 0.03% (whichever is lower) for Intraday, Futures, Options.
        # Free for Delivery.
        if trade_type == "DELIVERY":
            brokerage = 0.0
        elif trade_type in ("INTRADAY", "FUTURES", "OPTIONS"):
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
                stt = turnover * 0.0001  # 0.01% CTT on sell only (futures)
        elif trade_type == "OPTIONS":
            if direction == "SELL":
                stt = turnover * 0.0005  # 0.05% on sell-side premium (options)

        # 3. Exchange Transaction Charges (NSE standard)
        if trade_type == "FUTURES":
            exchange_charges = turnover * 0.000019  # 0.0019%
        elif trade_type == "OPTIONS":
            exchange_charges = turnover * 0.00053  # 0.053% on premium
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
            elif trade_type == "OPTIONS":
                stamp_duty = turnover * 0.00003  # 0.003% (equity index options)

        total_charges = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
        return brokerage, stt, exchange_charges, gst, sebi_charges, stamp_duty, total_charges

    def match_order(self, order: Order, candle: Any, timestamp: str) -> Optional[Trade]:
        """
        Attempts to match an order against a candle.
        Accepts Candle objects, pandas Series, or plain dicts (live path).
        Returns a Trade object if filled, otherwise None.
        """
        if order.status != "PENDING":
            return None

        # Helper: extract OHLCV field regardless of input type (Candle, Series, dict)
        def _get(field: str, default=0.0):
            if isinstance(candle, dict):
                return candle.get(field, default)
            if hasattr(candle, field):
                return getattr(candle, field)
            if hasattr(candle, '__getitem__'):
                try:
                    return candle[field]
                except Exception:
                    return default
            return default

        is_filled = False
        fill_price = 0.0
        slippage_value = 0.0

        # slippage calculation: BUY price goes up, SELL price goes down.
        sign = 1 if order.direction == "BUY" else -1

        open_p = float(_get("open", 0.0))
        high_p = float(_get("high", 0.0))
        low_p = float(_get("low", 0.0))

        if order.type == "MARKET":
            # Market orders fill at the candle's open price
            fill_price = open_p
            slippage_value = fill_price * self.slippage_pct * sign
            fill_price += slippage_value
            is_filled = True

        elif order.type == "LIMIT":
            # For Limit Buy, price must be high enough to match low (candle low <= order price)
            if order.direction == "BUY":
                if low_p <= order.price:
                    fill_price = order.price  # Limit orders fill at limit price or better
                    slippage_value = fill_price * self.slippage_pct
                    # Limit buys get filled at limit price + slippage (pessimistic modeling)
                    fill_price += slippage_value
                    is_filled = True
            # For Limit Sell, price must be low enough to match high (candle high >= order price)
            elif order.direction == "SELL":
                if high_p >= order.price:
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
            trade_type = self.default_trade_type
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
