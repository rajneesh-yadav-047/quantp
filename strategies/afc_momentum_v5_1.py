"""
AI Momentum Strategy for AFC @ FIFTEEN_MINUTE — v5.1
50-bar SMA to reduce whipsaws. 50 shares to make fees manageable.

Strategy v5.1 Logic:
  1. 50-bar SMA = primary trend (slower = fewer flips)
  2. Always in market
       - Price > 50-SMA → LONG 50 shares
       - Price < 50-SMA → SHORT 50 shares
  3. Flip when SMA direction changes
  4. Cooldown: 2 bars (skip one bar after flip to avoid noise)
"""

class Strategy:
    def __init__(self):
        self.name = "AI Momentum SMA AFC v5.1"
        self.sma_period = 50
        self.max_position = 50
        self.cooldown_bars = 2
        self.last_trade_bar = -100

    def _sma(self, values, period):
        if len(values) < period:
            return None
        return sum(values[-period:]) / period

    def on_bar(self, state):
        orders = []
        symbol = list(state.current_candle.keys())[0]
        candle = state.current_candle[symbol]
        candles = state.historical_candles.get(symbol, [])
        pos = state.positions.get(symbol)

        if len(candles) < self.sma_period + 2:
            return orders

        current_close = float(candle.close)
        closes = [c.close for c in candles]
        sma = self._sma(closes, self.sma_period)
        if sma is None:
            return orders

        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown_bars:
            return orders

        desired_long = current_close > sma
        desired_short = current_close < sma
        current_qty = pos.qty if pos else 0

        if desired_long and current_qty <= 0:
            qty = self.max_position + abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[MOM-v5.1] LONG @ {current_close} | SMA={round(sma,2)} | Qty={qty}")

        elif desired_short and current_qty >= 0:
            qty = self.max_position + abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "SELL",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[MOM-v5.1] SHORT @ {current_close} | SMA={round(sma,2)} | Qty={qty}")

        return [o for o in orders if o.get("qty", 0) > 0]
