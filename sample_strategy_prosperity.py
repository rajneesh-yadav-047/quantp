"""
Sample Prosperity Strategy — QuantLab Prosperity Runtime
========================================================

Runtime type:  prosperity_trader
Expected entrypoint:  None (auto-detected from class name Trader)

Symbols:  NSE:SBIN-EQ
Interval: FIVE_MINUTE

How to use:
  1. Copy this code into the QuantLab strategy editor
  2. Set runtime_type to "prosperity_trader"
  3. Set symbols to ["NSE:SBIN-EQ"]
  4. Run backtest or live deployment

The Prosperity runtime calls trader.run(state) each tick and expects:
    orders, conversions, trader_data = trader.run(state)

State object (TradingState) provides:
    - state.timestamp          -> str (ISO timestamp)
    - state.order_depths       -> dict {symbol: OrderDepth}
    - state.own_trades         -> dict {symbol: [Trade, ...]}  (your fills this tick)
    - state.market_trades      -> dict {symbol: [Trade, ...]}  (all market trades)
    - state.positions          -> dict {symbol: Position}     (current holdings)
    - state.position           -> dict {symbol: int}          (qty only, convenience)
    - state.portfolio_value     -> float (total equity)
    - state.cash               -> float (available cash)
    - state.trader_data        -> str  (JSON persisted across ticks — YOUR memory)
    - state.listings           -> dict {symbol: Listing}
    - state.observations       -> dict {name: Observation}

OrderDepth provides:
    - depth.buy_orders   -> dict {price: volume}  (bids, best first)
    - depth.sell_orders  -> dict {price: volume}  (asks, best first)
    - depth.best_bid()   -> (price, volume) or None
    - depth.best_ask()   -> (price, volume) or None

Order placement (Prosperity style):
    Order(symbol, price, quantity)
    # Positive quantity = BUY, Negative quantity = SELL
"""

import json
from typing import List, Dict, Any

# These classes are injected into the sandbox by the runtime engine:
#   Order, OrderDepth, Trade, Position, Listing, TradingState, Logger
# You do NOT need to import them in your strategy code.

class Trader:
    def __init__(self):
        # In-memory state (reset each backtest run, not persisted across ticks)
        self.fast_window = 9
        self.slow_window = 21
        self.closes: Dict[str, List[float]] = {}  # symbol -> list of close prices

    def run(self, state: Any) -> tuple:
        """
        Called on every tick (candle update).

        Returns:
            (orders, conversions, trader_data)
            - orders:      List[Order]  — orders to submit this tick
            - conversions: List[Order] — usually empty for equity strategies
            - trader_data: str          — JSON string, persisted across ticks
        """
        # ── 1. Restore persistent state from previous tick ─────────
        trader_data = self._load_trader_data(state.trader_data)

        # ── 2. Select symbol ───────────────────────────────────────
        symbol = "NSE:SBIN-EQ"
        # For multi-symbol, iterate state.order_depths.keys()

        # ── 3. Extract order book / price ──────────────────────────
        order_depth = state.order_depths.get(symbol)
        if order_depth is None:
            return [], [], json.dumps(trader_data)

        best_bid = order_depth.best_bid()
        best_ask = order_depth.best_ask()
        if best_bid is None or best_ask is None:
            return [], [], json.dumps(trader_data)

        mid_price = (best_bid[0] + best_ask[0]) / 2.0

        # ── 4. Build price history ─────────────────────────────────
        if symbol not in self.closes:
            self.closes[symbol] = []
        self.closes[symbol].append(mid_price)
        # Keep only what we need for EMA calculation
        history = self.closes[symbol]
        if len(history) > self.slow_window * 2:
            self.closes[symbol] = history[-self.slow_window * 2:]

        # ── 5. Not enough history yet? ─────────────────────────────
        if len(history) < self.slow_window:
            return [], [], json.dumps(trader_data)

        # ── 6. Compute EMA crossover ───────────────────────────────
        fast_ema = self._ema(history, self.fast_window)
        slow_ema = self._ema(history, self.slow_window)

        prev_history = history[:-1]
        prev_fast = self._ema(prev_history, self.fast_window) if len(prev_history) >= self.fast_window else fast_ema
        prev_slow = self._ema(prev_history, self.slow_window) if len(prev_history) >= self.slow_window else slow_ema

        # ── 7. Current position ────────────────────────────────────
        current_qty = state.position.get(symbol, 0)

        # ── 8. Signal & Order logic ────────────────────────────────
        orders: List[Any] = []

        # Golden cross: fast EMA crosses above slow EMA -> BUY
        if prev_fast <= prev_slow and fast_ema > slow_ema:
            if current_qty <= 0:
                # Place MARKET-style buy at best ask price
                qty = 14  # Adjust to your max_position_size / capital
                # Order(symbol, price, quantity) — positive = BUY
                orders.append(Order(symbol, best_ask[0], qty))

        # Death cross: fast EMA crosses below slow EMA -> SELL
        elif prev_fast >= prev_slow and fast_ema < slow_ema:
            if current_qty > 0:
                # Place MARKET-style sell at best bid price
                # Negative quantity = SELL
                orders.append(Order(symbol, best_bid[0], -current_qty))

        # ── 9. Save persistent state ─────────────────────────────────
        trader_data["closes_count"] = len(history)
        trader_data["last_fast_ema"] = round(fast_ema, 2)
        trader_data["last_slow_ema"] = round(slow_ema, 2)

        return orders, [], json.dumps(trader_data)

    # ── Helper: EMA calculator ───────────────────────────────────
    def _ema(self, values: List[float], period: int) -> float:
        """Compute exponential moving average of a list of numbers."""
        if len(values) < period:
            return values[-1] if values else 0.0
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
        return ema

    # ── Helper: trader_data JSON decode ───────────────────────────
    def _load_trader_data(self, raw: str) -> Dict[str, Any]:
        """Parse the persisted trader_data JSON string."""
        try:
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return {}


# ═══════════════════════════════════════════════════════════════
#  Alternative: Multi-Symbol Prosperity Strategy Skeleton
# ═══════════════════════════════════════════════════════════════
#   class Trader:
#       def run(self, state):
#           orders = []
#           trader_data = self._load_trader_data(state.trader_data)
#           for symbol in state.order_depths:
#               depth = state.order_depths[symbol]
#               qty = state.position.get(symbol, 0)
#               # ... per-symbol logic ...
#               if should_buy:
#                   orders.append(Order(symbol, depth.best_ask()[0], 10))
#               elif should_sell and qty > 0:
#                   orders.append(Order(symbol, depth.best_bid()[0], -qty))
#           return orders, [], json.dumps(trader_data)
#
#   NOTE: Do NOT import Order from anywhere. The runtime injects it.
#   If you need other standard libraries (json, math, typing), they
#   are available in the sandbox. Avoid os, sys, subprocess, requests.
# ═══════════════════════════════════════════════════════════════
