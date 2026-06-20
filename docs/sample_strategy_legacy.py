"""
Sample Legacy Strategy — QuantLab on_bar Runtime
===============================================

Runtime type:  legacy_on_bar
Expected entrypoint:  None (auto-detected from class name Strategy)

Symbols:  NSE:SBIN-EQ
Interval: FIVE_MINUTE

How to use:
  1. Copy this code into the QuantLab strategy editor
  2. Set runtime_type to "legacy_on_bar"
  3. Set symbols to ["NSE:SBIN-EQ"]
  4. Run backtest or live deployment

The backtest engine creates a MarketState object each tick and passes it
to your on_bar() method. You return a list of order dicts.
"""

class Strategy:
    def __init__(self):
        # Persistent state across ticks (backtest engine preserves the instance)
        self.fast_ema = None      # 9-period EMA tracker
        self.slow_ema = None      # 21-period EMA tracker
        self.bar_count = 0
        self.last_signal = None   # "BUY" | "SELL" | None

    def on_bar(self, state):
        """
        Called on every new candle tick.

        Args:
            state: MarketState object with:
                - state.current_time              -> str (ISO timestamp)
                - state.current_candle            -> dict {symbol: Candle}
                - state.historical_candles        -> dict {symbol: [Candle, ...]}
                - state.positions                 -> dict {symbol: Position}
                - state.portfolio                 -> Portfolio (cash, equity, pnl)
                - state.active_orders             -> list of pending/filled Orders

        Returns:
            list of order dicts, e.g.:
            [
                {
                    "symbol": "NSE:SBIN-EQ",
                    "direction": "BUY",
                    "type": "MARKET",   # "MARKET" or "LIMIT"
                    "price": 0.0,       # 0.0 for MARKET, limit price for LIMIT
                    "qty": 10,
                }
            ]
        """
        # ── 1. Select symbol ──────────────────────────────────────
        symbol = "NSE:SBIN-EQ"
        # For multi-symbol strategies, iterate state.current_candle.keys()

        # ── 2. Get current candle ─────────────────────────────────
        candle = state.current_candle.get(symbol)
        if candle is None:
            return []  # No data for this tick

        close_price = candle.close
        self.bar_count += 1

        # ── 3. Compute EMAs manually (or from historical_candles) ─
        hist = state.historical_candles.get(symbol, [])
        closes = [c.close for c in hist] + [close_price]

        if len(closes) < 21:
            return []  # Not enough history yet

        self.fast_ema = self._ema(closes, 9)
        self.slow_ema = self._ema(closes, 21)

        prev_fast = self._ema(closes[:-1], 9)
        prev_slow = self._ema(closes[:-1], 21)

        # ── 4. Position check ─────────────────────────────────────
        current_pos = state.positions.get(symbol)
        current_qty = current_pos.qty if current_pos else 0

        # ── 5. Signal logic ───────────────────────────────────────
        orders = []

        # Golden cross: fast crosses above slow -> BUY
        if prev_fast <= prev_slow and self.fast_ema > self.slow_ema:
            if current_qty <= 0:
                # Close short + go long (or just open long)
                qty = 14  # Adjust to your max_position_size
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": qty,
                })
                self.last_signal = "BUY"

        # Death cross: fast crosses below slow -> SELL
        elif prev_fast >= prev_slow and self.fast_ema < self.slow_ema:
            if current_qty > 0:
                # Close long position
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": current_qty,  # Sell entire position
                })
                self.last_signal = "SELL"

        # ── 6. Return orders ──────────────────────────────────────
        return orders

    # ── Helper: EMA calculator ──────────────────────────────────
    def _ema(self, values, period):
        """Compute exponential moving average of a list of numbers."""
        if len(values) < period:
            return values[-1] if values else 0.0
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
        return ema


# ═══════════════════════════════════════════════════════════════
#  Alternative: Old-style on_bar(df, i) signature (also supported)
# ═══════════════════════════════════════════════════════════════
# The LegacyRuntime auto-detects whether your on_bar takes 2 args (state)
# or 3 args (self, df, i). Below is the OLD signature for reference:
#
#   class Strategy:
#       def on_bar(self, df, i):
#           # df = pandas DataFrame with columns [time, open, high, low, close, volume]
#           # i  = current row index (0-based)
#           close = df.iloc[i]["close"]
#           # ... signal logic ...
#           return [{"symbol": "NSE:SBIN-EQ", "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": 10}]
#
# This is kept for backward compatibility but the new state-based
# signature above is recommended for multi-symbol and live trading.
# ═══════════════════════════════════════════════════════════════
