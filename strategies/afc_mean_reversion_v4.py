"""
AI Trend-Aligned Channel Strategy for AFC @ FIFTEEN_MINUTE — v4.0
Tuned from Research Lab analysis — 676 bars

Research Verdict:
  - Best-fit: MEAN_REVERSION (score 100/100) — but data shows downtrend bias
  - Trend: NEUTRAL per research | Actual: DOWNTREND 500→490
  - Vol Regime: LOW (2.25% ann. vol)
  - Regimes: QUIET_RANGING 35.8% + VOLATILE_RANGING 33.7% = 69.5% range-bound

Strategy v4 Logic (Trend-Aligned Channel Fade):
  1. 50-bar SMA = trend filter
       - Price < 50-SMA → DOWNTREND → only SHORT entries (fade rallies)
       - Price > 50-SMA → UPTREND → only LONG entries (buy dips)
  2. 20-bar High/Low Channel = entry/exit levels
       - SHORT entry: price in top 15% of channel (rally to fade)
       - LONG entry: price in bottom 15% of channel (dip to buy)
  3. Exit: opposite edge of channel (ride the full move)
       - SHORT exit: price at or below channel low (full fade complete)
       - LONG exit: price at or above channel high
  4. Stop: beyond the entry-side channel edge (breakout stop)
  5. MARKET orders — guaranteed fill
  6. Cooldown: 3 bars | Position: 10 shares
  7. No time stop — let trend-aligned trades run
"""

import math


class Strategy:
    def __init__(self):
        self.name = "AI Trend-Aligned Channel AFC v4.0"

        # ── Parameters ──
        self.trend_period = 50        # SMA for trend direction
        self.channel_period = 20      # channel for entries/exits
        self.entry_zone_pct = 0.15    # top/bottom 15%
        self.cooldown_bars = 3
        self.max_position = 10

        # ── State ──
        self.last_trade_bar = -100

    # ── Helpers ──

    def _sma(self, values, period):
        if len(values) < period:
            return None
        return sum(values[-period:]) / period

    def _channel(self, candles, period):
        if len(candles) < period:
            return None, None, None
        highs = [c.high for c in candles[-period:]]
        lows = [c.low for c in candles[-period:]]
        ch_high = max(highs)
        ch_low = min(lows)
        ch_mid = (ch_high + ch_low) / 2.0
        return ch_high, ch_low, ch_mid

    # ── Main entry point ──

    def on_bar(self, state):
        orders = []

        symbol = list(state.current_candle.keys())[0]
        candle = state.current_candle[symbol]
        candles = state.historical_candles.get(symbol, [])
        pos = state.positions.get(symbol)

        need_bars = max(self.trend_period, self.channel_period) + 2
        if len(candles) < need_bars:
            return orders

        current_close = float(candle.close)
        current_high = float(candle.high)
        current_low = float(candle.low)

        # ── Indicators ──
        closes = [c.close for c in candles]
        sma = self._sma(closes, self.trend_period)
        ch_high, ch_low, ch_mid = self._channel(candles, self.channel_period)
        if sma is None or ch_high is None:
            return orders

        channel_width = ch_high - ch_low
        if channel_width <= 0:
            return orders

        position_in_channel = (current_close - ch_low) / channel_width
        in_bottom_zone = position_in_channel <= self.entry_zone_pct
        in_top_zone = position_in_channel >= (1.0 - self.entry_zone_pct)

        # Trend direction
        in_downtrend = current_close < sma
        in_uptrend = current_close > sma

        # ── Cooldown ──
        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown_bars:
            return orders

        if not pos or pos.qty == 0:
            # ── No position: trend-aligned entries only ──

            if in_downtrend and in_top_zone:
                # DOWNTREND: fade rally at channel high
                stop_price = round(ch_high + 0.05 * channel_width, 2)
                target_price = round(ch_low, 2)
                qty = self.max_position

                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar = current_bar_idx
                print(f"[MR-v4] SHORT entry @ {current_close} | Trend=DOWN SMA={round(sma,2)} | Channel=[{round(ch_low,2)}, {round(ch_high,2)}] | Target={target_price} | Stop={stop_price}")

            elif in_uptrend and in_bottom_zone:
                # UPTREND: buy dip at channel low
                stop_price = round(ch_low - 0.05 * channel_width, 2)
                target_price = round(ch_high, 2)
                qty = self.max_position

                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar = current_bar_idx
                print(f"[MR-v4] LONG entry @ {current_close} | Trend=UP SMA={round(sma,2)} | Channel=[{round(ch_low,2)}, {round(ch_high,2)}] | Target={target_price} | Stop={stop_price}")

        else:
            # ── In position: exit at opposite channel edge ──
            if pos.qty > 0:
                # LONG: exit at channel high (full reversion + trend continuation)
                if current_close >= ch_high:
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v4] LONG exit @ {current_close} | Channel high reached={round(ch_high,2)}")

                elif current_low <= ch_low:
                    # Stop: broke below channel low (range broken against us)
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v4] LONG stop @ {current_close} | Broke channel low={round(ch_low,2)}")

            elif pos.qty < 0:
                # SHORT: exit at channel low (full fade complete)
                if current_close <= ch_low:
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v4] SHORT exit @ {current_close} | Channel low reached={round(ch_low,2)}")

                elif current_high >= ch_high:
                    # Stop: broke above channel high (range broken against us)
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    self.last_trade_bar = current_bar_idx
                    print(f"[MR-v4] SHORT stop @ {current_close} | Broke channel high={round(ch_high,2)}")

        return [o for o in orders if o.get("qty", 0) > 0]
