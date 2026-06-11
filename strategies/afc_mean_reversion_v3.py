"""
AI Mean Reversion Strategy for AFC @ FIFTEEN_MINUTE — v3.0
Tuned from Research Lab analysis — 676 bars

Research Verdict:
  - Best-fit: MEAN_REVERSION (score 100/100)
  - Trend: NEUTRAL | Vol Regime: LOW (2.25% ann. vol)
  - ADX-proxy: 22.21 (weak trend, ranging dominates)
  - Avg Range: Rs.0.64 | Body/Range: 0.517 (mixed, some wicks)
  - Sharpe: -0.6 (weak drift — timing edge required)
  - Skewness: -0.134 (slight negative tail)
  - Autocorr lag-1: 0.008 (no momentum, pure mean-reversion)
  - Bar Bias: 49.5% (direction-agnostic)
  - Regimes: QUIET_RANGING 35.8% + VOLATILE_RANGING 33.7% = 69.5% range-bound

Strategy v3 Logic (Momentum-Confirmed Channel Reversion):
  1. Rolling 50-bar High/Low Channel — wider range = bigger profit potential
  2. Entry zone: bottom 10% / top 10% only (more extreme = better edge)
  3. Exhaustion filter: only fade if the bar shows reversal pressure
       - LONG: price in bottom 10% AND close > open (buying at the low)
       - SHORT: price in top 10% AND close < open (selling at the high)
  4. No flip logic — close position first, then evaluate new entry
  5. Target: channel midpoint (mean reversion complete)
  6. Stop: opposite channel edge (if range breaks, exit immediately)
  7. Time stop: exit after 8 bars if target not hit (avoid dead trades)
  8. Range quality filter: only trade if channel width > 2× avg_range
  9. MARKET orders — guaranteed fill at next open
  10. Cooldown: 2 bars | Position: 5 shares (fees are % of smaller P&L)
"""

import math


class Strategy:
    def __init__(self):
        self.name = "AI Mean Reversion AFC v3.0 — Exhaustion"

        # ── Research-tuned parameters ──
        self.channel_period = 50      # wider channel for bigger targets
        self.entry_zone_pct = 0.10    # bottom/top 10% = more extreme entries
        self.cooldown_bars = 2
        self.max_position = 5         # smaller size = fees hurt less
        self.avg_range = 0.64
        self.min_channel_width = 2.0 * self.avg_range  # Rs.1.28 minimum
        self.max_hold_bars = 8        # time stop

        # ── State ──
        self.last_trade_bar = -100
        self.entry_bar_idx = -100
        self.entry_direction = None   # "LONG" or "SHORT"

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
        current_open = float(candle.open)
        current_high = float(candle.high)
        current_low = float(candle.low)

        # ── Channel Indicators ──
        ch_high, ch_low, ch_mid = self._channel(candles, self.channel_period)
        if ch_high is None or ch_low is None:
            return orders

        channel_width = ch_high - ch_low
        if channel_width <= 0:
            return orders

        # ── Range quality filter ──
        if channel_width < self.min_channel_width:
            return orders  # too compressed, no room for profit after fees

        # Position within channel (0 = at low, 1 = at high)
        position_in_channel = (current_close - ch_low) / channel_width

        # Bar direction (bullish or bearish)
        bar_bullish = current_close > current_open
        bar_bearish = current_close < current_open

        # ── Cooldown check ──
        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown_bars:
            return orders

        # ── Zone flags ──
        in_bottom_zone = position_in_channel <= self.entry_zone_pct
        in_top_zone = position_in_channel >= (1.0 - self.entry_zone_pct)
        at_or_above_mid = current_close >= ch_mid
        at_or_below_mid = current_close <= ch_mid

        # ── Time stop check ──
        bars_held = current_bar_idx - self.entry_bar_idx
        if pos and pos.qty != 0 and bars_held >= self.max_hold_bars:
            # Time stop: exit position
            if pos.qty > 0:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": abs(pos.qty),
                })
                self.last_trade_bar = current_bar_idx
                self.entry_bar_idx = -100
                self.entry_direction = None
                print(f"[MR-v3] LONG time-stop exit @ {current_close} | Held {bars_held} bars")
                return orders
            elif pos.qty < 0:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": abs(pos.qty),
                })
                self.last_trade_bar = current_bar_idx
                self.entry_bar_idx = -100
                self.entry_direction = None
                print(f"[MR-v3] SHORT time-stop exit @ {current_close} | Held {bars_held} bars")
                return orders

        if not pos or pos.qty == 0:
            # ── No position: look for new entry ──
            # LONG: bottom zone + bullish bar (exhaustion at lows)
            if in_bottom_zone and bar_bullish:
                stop_price = round(ch_low - 0.05 * channel_width, 2)  # just below channel low
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
                self.entry_bar_idx = current_bar_idx
                self.entry_direction = "LONG"
                print(f"[MR-v3] LONG entry @ {current_close} | Channel=[{round(ch_low,2)}, {round(ch_high,2)}] width={round(channel_width,2)} | Mid={round(ch_mid,2)} | Pos={round(position_in_channel,2)} | Bullish bar | Stop={stop_price} | Target={target_price}")

            # SHORT: top zone + bearish bar (exhaustion at highs)
            elif in_top_zone and bar_bearish:
                stop_price = round(ch_high + 0.05 * channel_width, 2)  # just above channel high
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
                self.entry_bar_idx = current_bar_idx
                self.entry_direction = "SHORT"
                print(f"[MR-v3] SHORT entry @ {current_close} | Channel=[{round(ch_low,2)}, {round(ch_high,2)}] width={round(channel_width,2)} | Mid={round(ch_mid,2)} | Pos={round(position_in_channel,2)} | Bearish bar | Stop={stop_price} | Target={target_price}")

        else:
            # ── In position: manage exits ──
            if pos.qty > 0:
                # LONG position
                if at_or_above_mid:
                    # Target hit: exit at midpoint
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    self.entry_bar_idx = -100
                    self.entry_direction = None
                    print(f"[MR-v3] LONG exit @ {current_close} | Midpoint reached | Channel mid={round(ch_mid,2)}")

                elif current_low <= ch_low:
                    # Stop hit: price broke below channel low (range broken)
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    self.entry_bar_idx = -100
                    self.entry_direction = None
                    print(f"[MR-v3] LONG stop @ {current_close} | Broke channel low={round(ch_low,2)}")

            elif pos.qty < 0:
                # SHORT position
                if at_or_below_mid:
                    # Target hit: exit at midpoint
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    self.entry_bar_idx = -100
                    self.entry_direction = None
                    print(f"[MR-v3] SHORT exit @ {current_close} | Midpoint reached | Channel mid={round(ch_mid,2)}")

                elif current_high >= ch_high:
                    # Stop hit: price broke above channel high (range broken)
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    self.entry_bar_idx = -100
                    self.entry_direction = None
                    print(f"[MR-v3] SHORT stop @ {current_close} | Broke channel high={round(ch_high,2)}")

        # Filter zero-qty orders
        return [o for o in orders if o.get("qty", 0) > 0]
