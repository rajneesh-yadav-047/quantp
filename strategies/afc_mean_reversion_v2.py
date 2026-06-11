"""
AI Mean Reversion Strategy for AFC @ FIFTEEN_MINUTE — v2.0
Tuned from Research Lab analysis — 676 bars

Research Verdict:
  - Best-fit: MEAN_REVERSION (score 100/100)
  - Trend: NEUTRAL | Vol Regime: LOW (2.25% ann. vol)
  - ADX-proxy: 22.21 (weak trend, ranging dominates)
  - Avg Range: ₹0.64 | Body/Range: 0.517 (mixed, some wicks)
  - Sharpe: -0.6 (weak drift — timing edge required)
  - Skewness: -0.134 (slight negative tail)
  - Autocorr lag-1: 0.008 (no momentum, pure mean-reversion)
  - Bar Bias: 49.5% (direction-agnostic)
  - Nearest Resistance: ₹490.84
  - Regimes: QUIET_RANGING 35.8% + VOLATILE_RANGING 33.7% = 69.5% range-bound

Strategy v2 Logic (Channel Mean Reversion):
  1. Rolling 20-bar High/Low Channel — captures the recent trading range
  2. Entry: price in bottom 15% of channel → LONG (fade the low)
           price in top 15% of channel → SHORT (fade the high)
  3. Exit: price reaches channel midpoint → mean reversion complete
  4. Flip: if long and price hits top 15% → flip to short
           if short and price hits bottom 15% → flip to long
  5. Stop: 1.5× channel width beyond entry (wide, let mean reversion work)
  6. MARKET orders — guaranteed fill at next open
  7. Cooldown: 2 bars between trades
  8. No time filter — trade all day, 69.5% ranging regime
  9. No RSI — in 2.25% vol, RSI extremes are rare and unnecessary
"""

import math


class Strategy:
    def __init__(self):
        self.name = "AI Mean Reversion AFC v2.0 — Channel"

        # ── Research-tuned parameters ──
        self.channel_period = 20      # rolling channel lookback
        self.entry_zone_pct = 0.15    # bottom/top 15% of channel = entry zone
        self.cooldown_bars = 2
        self.max_position = 10
        self.stop_multiplier = 1.5    # stop = 1.5 × channel width beyond entry
        self.resistance_level = 490.84
        self.avg_range = 0.64

        # ── State ──
        self.last_trade_bar = -100

    # ── Helpers ──

    def _channel(self, candles, period):
        """Return (channel_high, channel_low, channel_mid) for last N candles."""
        if len(candles) < period:
            return None, None, None
        highs = [c.high for c in candles[-period:]]
        lows = [c.low for c in candles[-period:]]
        ch_high = max(highs)
        ch_low = min(lows)
        ch_mid = (ch_high + ch_low) / 2.0
        return ch_high, ch_low, ch_mid

    def _hour_from_ts(self, ts):
        """Extract hour from timestamp string."""
        if " " in ts:
            time_part = ts.split(" ")[1]
            return int(time_part.split(":")[0])
        if "T" in ts:
            time_part = ts.split("T")[1]
            return int(time_part.split(":")[0])
        return 0

    # ── Main entry point ──

    def on_bar(self, state):
        orders = []

        # Get symbol dynamically
        symbol = list(state.current_candle.keys())[0]
        candle = state.current_candle[symbol]
        candles = state.historical_candles.get(symbol, [])
        pos = state.positions.get(symbol)

        # Need enough data for channel
        if len(candles) < self.channel_period + 2:
            return orders

        current_close = float(candle.close)
        current_high = float(candle.high)
        current_low = float(candle.low)

        # ── Channel Indicators ──
        ch_high, ch_low, ch_mid = self._channel(candles, self.channel_period)
        if ch_high is None or ch_low is None:
            return orders

        channel_width = ch_high - ch_low
        if channel_width <= 0:
            return orders

        # Position within channel (0 = at low, 1 = at high)
        position_in_channel = (current_close - ch_low) / channel_width

        # ── Cooldown check ──
        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown_bars:
            return orders

        # ── Entry / Exit / Flip Logic ──
        in_bottom_zone = position_in_channel <= self.entry_zone_pct
        in_top_zone = position_in_channel >= (1.0 - self.entry_zone_pct)
        at_or_above_mid = current_close >= ch_mid
        at_or_below_mid = current_close <= ch_mid

        if not pos or pos.qty == 0:
            # ── No position: look for new entry ──
            if in_bottom_zone:
                # LONG: fade the low
                stop_price = round(current_close - self.stop_multiplier * channel_width, 2)
                target_price = round(ch_mid, 2)
                qty = self.max_position

                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar = current_bar_idx
                print(f"[MR-v2] LONG entry @ {current_close} | Channel=[{round(ch_low,2)}, {round(ch_high,2)}] | Mid={round(ch_mid,2)} | Pos={round(position_in_channel,2)} | Stop={stop_price} | Target={target_price}")

            elif in_top_zone:
                # SHORT: fade the high
                stop_price = round(current_close + self.stop_multiplier * channel_width, 2)
                target_price = round(ch_mid, 2)
                qty = self.max_position

                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar = current_bar_idx
                print(f"[MR-v2] SHORT entry @ {current_close} | Channel=[{round(ch_low,2)}, {round(ch_high,2)}] | Mid={round(ch_mid,2)} | Pos={round(position_in_channel,2)} | Stop={stop_price} | Target={target_price}")

        else:
            # ── In position: manage exit and flips ──
            if pos.qty > 0:
                # Currently LONG
                if in_top_zone:
                    # Flip to SHORT: exit long, enter short
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty) + self.max_position,  # close + reverse
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v2] LONG→SHORT flip @ {current_close} | Pos={round(position_in_channel,2)} | Closed long, opened short")

                elif at_or_above_mid:
                    # Exit long at midpoint (mean reversion complete)
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v2] LONG exit @ {current_close} | Midpoint reached | Channel mid={round(ch_mid,2)}")

            elif pos.qty < 0:
                # Currently SHORT
                if in_bottom_zone:
                    # Flip to LONG: exit short, enter long
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty) + self.max_position,  # close + reverse
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v2] SHORT→LONG flip @ {current_close} | Pos={round(position_in_channel,2)} | Closed short, opened long")

                elif at_or_below_mid:
                    # Exit short at midpoint
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v2] SHORT exit @ {current_close} | Midpoint reached | Channel mid={round(ch_mid,2)}")

        # Filter zero-qty orders
        return [o for o in orders if o.get("qty", 0) > 0]
