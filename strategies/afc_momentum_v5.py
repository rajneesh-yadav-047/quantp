"""
AI Momentum Strategy for AFC @ FIFTEEN_MINUTE — v5.0
Simple SMA crossover — always in market, ride the trend.

Research said mean reversion, but data shows downtrend 500→490.
Mean reversion fails because edge < fees. Momentum captures the drift.

Strategy v5 Logic:
  1. 20-bar SMA = primary trend direction
  2. Always in market — no idle cash
       - Price > 20-SMA → LONG 10 shares
       - Price < 20-SMA → SHORT 10 shares
  3. When SMA direction flips, flip position
  4. No stops, no targets — let the trend run
  5. Cooldown: 1 bar (avoid whipsaw on SMA touch)
"""

class Strategy:
    def __init__(self):
        self.name = "AI Momentum SMA AFC v5.0"
        self.sma_period = 20
        self.max_position = 10
        self.cooldown_bars = 1
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

        # Determine desired position
        desired_long = current_close > sma
        desired_short = current_close < sma

        current_qty = pos.qty if pos else 0

        if desired_long and current_qty <= 0:
            # Need to be long (either flat or short)
            qty = self.max_position + abs(current_qty)  # open + close
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[MOM-v5] LONG @ {current_close} | SMA={round(sma,2)} | Qty={qty}")

        elif desired_short and current_qty >= 0:
            # Need to be short (either flat or long)
            qty = self.max_position + abs(current_qty)  # open + close
            orders.append({
                "symbol": symbol,
                "direction": "SELL",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[MOM-v5] SHORT @ {current_close} | SMA={round(sma,2)} | Qty={qty}")

        return [o for o in orders if o.get("qty", 0) > 0]
