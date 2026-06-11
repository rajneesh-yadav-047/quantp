"""
AI Downtrend Strategy for AFC @ FIFTEEN_MINUTE — v6.0
Only SHORT in confirmed downtrend. Capture the big move, pay minimal fees.

Data: AFC 500→490 over test period (~2% downtrend).
Strategy: Short when price < 50-SMA, cover when price > 50-SMA.
No long entries — stay flat in uptrends.

Strategy v6 Logic:
  1. 50-bar SMA = trend filter
  2. Flat when price > 50-SMA (no longs)
  3. SHORT 50 shares when price crosses below 50-SMA
  4. Cover (BUY 50) when price crosses above 50-SMA
  5. Cooldown: 3 bars after cover to avoid immediate re-entry
"""

class Strategy:
    def __init__(self):
        self.name = "AI Downtrend Only AFC v6.0"
        self.sma_period = 50
        self.max_position = 50
        self.cooldown_bars = 3
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

        current_qty = pos.qty if pos else 0

        # Downtrend confirmed: go short (or stay short)
        if current_close < sma and current_qty >= 0:
            # Enter short (or flip from long to short)
            qty = self.max_position + abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "SELL",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[DT-v6] SHORT @ {current_close} | SMA={round(sma,2)} | Qty={qty}")

        # Uptrend: cover short, go flat
        elif current_close > sma and current_qty < 0:
            qty = abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[DT-v6] COVER @ {current_close} | SMA={round(sma,2)} | Qty={qty}")

        return [o for o in orders if o.get("qty", 0) > 0]
