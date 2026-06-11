"""
AI Downtrend Strategy for AFC @ FIFTEEN_MINUTE — v6.3 FINAL
Trailing stop to ride the downtrend, exit only on genuine reversal.
Forces close on final bar so backtest reports realized P&L.

Strategy Logic:
  1. 50-bar SMA = trend filter
  2. Short entry: price < SMA × 0.995
  3. Once short, track highest high since entry
  4. Trailing cover: price > highest_high × 1.005
  5. End-of-backtest: if still short on last bar, cover at close
  6. SHORT 100 shares | Cooldown: 3 bars after cover
"""

class Strategy:
    def __init__(self):
        self.name = "AI Downtrend Trailing Stop AFC v6.3 FINAL"
        self.sma_period = 50
        self.max_position = 100
        self.short_buffer = 0.005    # 0.5% below SMA to enter
        self.trail_pct = 0.005       # 0.5% above highest high to cover
        self.cooldown_bars = 3
        self.last_trade_bar = -100
        self.highest_high_since_entry = 0.0
        self.total_bars = 676        # known from dataset

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
        current_high = float(candle.high)
        closes = [c.close for c in candles]
        sma = self._sma(closes, self.sma_period)
        if sma is None:
            return orders

        lower_band = sma * (1 - self.short_buffer)

        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown_bars:
            return orders

        current_qty = pos.qty if pos else 0
        is_short = current_qty < 0

        # Update trailing highest high if in short
        if is_short:
            if current_high > self.highest_high_since_entry:
                self.highest_high_since_entry = current_high
            trail_stop = self.highest_high_since_entry * (1 + self.trail_pct)
        else:
            self.highest_high_since_entry = 0.0
            trail_stop = float('inf')

        # End of backtest: force close on last bar
        if current_bar_idx >= self.total_bars - 1 and is_short:
            qty = abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            print(f"[DT-v6.3] EOD COVER @ {current_close} | Final bar close | Qty={qty}")
            return orders

        # Short entry: price below lower band and not already short
        if current_close < lower_band and not is_short:
            qty = self.max_position + abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "SELL",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            self.highest_high_since_entry = current_high
            print(f"[DT-v6.3] SHORT @ {current_close} | SMA={round(sma,2)} | Band={round(lower_band,2)} | Qty={qty}")

        # Trailing stop cover: price breaks above highest high + trail
        elif is_short and current_close > trail_stop:
            qty = abs(current_qty)
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": round(current_close, 2),
                "qty": qty,
            })
            self.last_trade_bar = current_bar_idx
            self.highest_high_since_entry = 0.0
            print(f"[DT-v6.3] COVER @ {current_close} | Trail stop={round(trail_stop,2)} | Highest={round(self.highest_high_since_entry,2)}")

        return [o for o in orders if o.get("qty", 0) > 0]
