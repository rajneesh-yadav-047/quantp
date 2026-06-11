"""
AI Downtrend Strategy for AFC @ FIFTEEN_MINUTE — v6.2
Asymmetric buffer: tight short entry, wide cover threshold.

Strategy v6.2 Logic:
  1. 50-bar SMA = trend center
  2. Short zone: price < SMA × 0.995 (tight — enter early in downtrend)
  3. Cover zone: price > SMA × 1.01 (wide — only cover on strong rally)
  4. Dead zone between bands → no action
  5. SHORT 100 shares, cover when trend clearly reverses
  6. Cooldown: 3 bars after cover
"""

class Strategy:
    def __init__(self):
        self.name = "AI Downtrend Asymmetric AFC v6.2"
        self.sma_period = 50
        self.max_position = 100
        self.short_buffer = 0.005   # 0.5% below SMA
        self.cover_buffer = 0.010   # 1.0% above SMA
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

        lower_band = sma * (1 - self.short_buffer)
        upper_band = sma * (1 + self.cover_buffer)

        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown_bars:
            return orders

        current_qty = pos.qty if pos else 0

        # Short zone: price below tight lower band
        if current_close < lower_band and current_qty >= 0:
            qty = self.max_position + abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "SELL",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[DT-v6.2] SHORT @ {current_close} | SMA={round(sma,2)} | ShortBand={round(lower_band,2)} | CoverBand={round(upper_band,2)} | Qty={qty}")

        # Cover zone: price above wide upper band (strong rally = trend reversal)
        elif current_close > upper_band and current_qty < 0:
            qty = abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[DT-v6.2] COVER @ {current_close} | SMA={round(sma,2)} | ShortBand={round(lower_band,2)} | CoverBand={round(upper_band,2)} | Qty={qty}")

        return [o for o in orders if o.get("qty", 0) > 0]
