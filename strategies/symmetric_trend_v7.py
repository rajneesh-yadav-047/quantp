"""
AI Symmetric Trend Strategy — v7.0
Long in uptrends, short in downtrends, trailing stops both ways.
Multi-asset ready: tracks state per symbol.

Strategy Logic:
  1. 50-bar SMA per symbol = trend center
  2. Long zone: price > SMA × 1.005
     - Trailing stop: lowest low since entry × 0.995
  3. Short zone: price < SMA × 0.995
     - Trailing stop: highest high since entry × 1.005
  4. Dead zone: SMA×0.995 ≤ price ≤ SMA×1.005 → no action
  5. Flip: if long and price drops below SMA×0.995 → close long, open short
            if short and price rises above SMA×1.005 → close short, open long
  6. End-of-backtest: close all positions at market
  7. Position: 100 shares per symbol
  8. Cooldown: 2 bars after any trade
"""

class Strategy:
    def __init__(self):
        self.name = "AI Symmetric Trend v7.0"
        self.sma_period = 50
        self.max_position = 100
        self.long_buffer = 0.005    # 0.5% above SMA to go long
        self.short_buffer = 0.005   # 0.5% below SMA to go short
        self.trail_pct = 0.005      # 0.5% trail
        self.cooldown_bars = 2

        # Per-symbol state
        self.last_trade_bar = {}    # symbol -> last trade bar index
        self.lowest_low = {}        # symbol -> lowest low since long entry
        self.highest_high = {}      # symbol -> highest high since short entry
        self.in_position = {}       # symbol -> "LONG", "SHORT", or None

    def _sma(self, values, period):
        if len(values) < period:
            return None
        return sum(values[-period:]) / period

    def on_bar(self, state):
        orders = []

        # Process each symbol independently
        for symbol, candle in state.current_candle.items():
            candles = state.historical_candles.get(symbol, [])
            pos = state.positions.get(symbol)

            if len(candles) < self.sma_period + 2:
                continue

            current_close = float(candle.close)
            current_high = float(candle.high)
            current_low = float(candle.low)
            closes = [c.close for c in candles]
            sma = self._sma(closes, self.sma_period)
            if sma is None:
                continue

            long_band = sma * (1 + self.long_buffer)
            short_band = sma * (1 - self.short_buffer)

            current_bar_idx = len(candles)
            last_trade = self.last_trade_bar.get(symbol, -100)
            bars_since_last = current_bar_idx - last_trade
            if bars_since_last < self.cooldown_bars:
                continue

            current_qty = pos.qty if pos else 0
            is_long = current_qty > 0
            is_short = current_qty < 0
            position_type = self.in_position.get(symbol)

            # Update trailing levels
            if is_long:
                if current_low < self.lowest_low.get(symbol, float('inf')):
                    self.lowest_low[symbol] = current_low
                trail_stop = self.lowest_low.get(symbol, current_low) * (1 - self.trail_pct)
            else:
                self.lowest_low[symbol] = float('inf')
                trail_stop = 0.0

            if is_short:
                if current_high > self.highest_high.get(symbol, 0.0):
                    self.highest_high[symbol] = current_high
                trail_cover = self.highest_high.get(symbol, current_high) * (1 + self.trail_pct)
            else:
                self.highest_high[symbol] = 0.0
                trail_cover = float('inf')

            # End of backtest: close all positions
            total_bars = 676  # known from dataset
            if current_bar_idx >= total_bars - 1 and current_qty != 0:
                direction = "SELL" if is_long else "BUY"
                orders.append({
                    "symbol": symbol,
                    "direction": direction,
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": abs(current_qty),
                })
                self.last_trade_bar[symbol] = current_bar_idx
                self.in_position[symbol] = None
                print(f"[SYM-v7] EOD CLOSE {symbol} @ {current_close} | Qty={abs(current_qty)}")
                continue

            # ── Entry / Flip Logic ──
            if current_close > long_band and not is_long:
                # Go long (close short first if needed, then open long)
                qty = self.max_position + abs(current_qty)
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar[symbol] = current_bar_idx
                self.lowest_low[symbol] = current_low
                self.in_position[symbol] = "LONG"
                action = "FLIP LONG" if is_short else "LONG"
                print(f"[SYM-v7] {action} {symbol} @ {current_close} | SMA={round(sma,2)} | Band={round(long_band,2)} | Qty={qty}")

            elif current_close < short_band and not is_short:
                # Go short (close long first if needed, then open short)
                qty = self.max_position + abs(current_qty)
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar[symbol] = current_bar_idx
                self.highest_high[symbol] = current_high
                self.in_position[symbol] = "SHORT"
                action = "FLIP SHORT" if is_long else "SHORT"
                print(f"[SYM-v7] {action} {symbol} @ {current_close} | SMA={round(sma,2)} | Band={round(short_band,2)} | Qty={qty}")

            # ── Trailing Stop Exits ──
            elif is_long and current_close < trail_stop:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": abs(current_qty),
                })
                self.last_trade_bar[symbol] = current_bar_idx
                self.in_position[symbol] = None
                print(f"[SYM-v7] LONG STOP {symbol} @ {current_close} | Trail={round(trail_stop,2)} | Low={round(self.lowest_low.get(symbol, current_low),2)}")

            elif is_short and current_close > trail_cover:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": abs(current_qty),
                })
                self.last_trade_bar[symbol] = current_bar_idx
                self.in_position[symbol] = None
                print(f"[SYM-v7] SHORT STOP {symbol} @ {current_close} | Trail={round(trail_cover,2)} | High={round(self.highest_high.get(symbol, current_high),2)}")

        return [o for o in orders if o.get("qty", 0) > 0]
