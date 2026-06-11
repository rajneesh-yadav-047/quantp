"""
AI Mean Reversion Strategy for AFC @ FIFTEEN_MINUTE
Tuned from Research Lab analysis — 676 bars

Research Verdict:
  - Best-fit: MEAN_REVERSION (score 100/100)
  - Trend: NEUTRAL | Vol Regime: LOW
  - ADX-proxy: 22.21 (weak trend, ranging dominates)
  - Avg Range: ₹0.64 | Body/Range: 0.517 (mixed)
  - Ann. Vol: 2.25% (low — tight stops, breakout compression watch)
  - Sharpe: -0.6 (weak drift — timing edge required)
  - Skewness: -0.134 (slight negative tail)
  - Autocorr lag-1: 0.008 (no momentum, pure mean-reversion)
  - Bar Bias: 49.5% (direction-agnostic)
  - Best Hour: 13:00 for entry edge
  - Nearest Resistance: ₹490.84 (profit target / short entry)
  - Regimes: QUIET_RANGING 35.8% + VOLATILE_RANGING 33.7% = 69.5% range-bound

Strategy Logic:
  1. Bollinger Bands (20, 2.0σ) — price outside bands = mean-reversion setup
  2. RSI (14) confirmation — avoid fading into strong momentum
  3. Time filter — only trade during best hour 13:00-14:00
  4. ATR-based stops — 1.5× avg_range (₹0.96) for stops
  5. Profit target — 1.0× avg_range (₹0.64) or resistance level
  6. Cooldown — 3 bars between trades to avoid overtrading
  7. No position when inventory = 0 — don't place stops flat
"""

import math


class Strategy:
    def __init__(self):
        self.name = "AI Mean Reversion AFC v1.0"

        # ── Research-tuned parameters ──
        self.bb_period = 20
        self.bb_std = 2.0
        self.rsi_period = 14
        self.rsi_overbought = 65
        self.rsi_oversold = 35
        self.atr_multiplier = 1.5      # stop = 1.5 × avg_range (~₹0.96)
        self.profit_target_atr = 1.0  # target = 1.0 × avg_range (~₹0.64)
        self.cooldown_bars = 3
        self.max_position = 10
        self.best_hour_start = 13
        self.best_hour_end = 14
        self.resistance_level = 490.84
        self.avg_range = 0.64

        # ── State ──
        self.last_trade_bar = -100
        self.cooldown = self.cooldown_bars

    # ── Helpers ──

    def _sma(self, values, period):
        if len(values) < period:
            return None
        return sum(values[-period:]) / period

    def _std(self, values, period):
        if len(values) < period:
            return None
        mean = sum(values[-period:]) / period
        variance = sum((x - mean) ** 2 for x in values[-period:]) / period
        return math.sqrt(variance)

    def _atr(self, candles, period):
        if len(candles) < period + 1:
            return None
        trs = []
        for i in range(1, len(candles)):
            prev = candles[i - 1]
            curr = candles[i]
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close),
            )
            trs.append(tr)
        if len(trs) < period:
            return None
        return sum(trs[-period:]) / period

    def _rsi(self, closes, period):
        if len(closes) < period + 1:
            return None
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        if len(gains) < period:
            return None
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _hour_from_ts(self, ts):
        """Extract hour from timestamp string."""
        # Handles "2026-06-10 13:30:00" or ISO formats
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

        # Need enough data
        if len(candles) < self.bb_period + 5:
            return orders

        closes = [c.close for c in candles]
        current_close = float(candle.close)
        current_high = float(candle.high)
        current_low = float(candle.low)

        # ── Indicators ──
        sma = self._sma(closes, self.bb_period)
        std = self._std(closes, self.bb_period)
        if sma is None or std is None:
            return orders

        upper_band = sma + self.bb_std * std
        lower_band = sma - self.bb_std * std

        rsi = self._rsi(closes, self.rsi_period)
        atr = self._atr(candles, 14)
        if atr is None:
            atr = self.avg_range  # fallback to research avg_range

        # ── Time filter (best hour 13:00-14:00) ──
        hour = self._hour_from_ts(state.current_time)
        in_best_hour = self.best_hour_start <= hour < self.best_hour_end

        # ── Cooldown check ──
        current_bar_idx = len(candles)
        bars_since_last = current_bar_idx - self.last_trade_bar
        if bars_since_last < self.cooldown:
            return orders

        # ── Mean Reversion Entry Logic ──
        # Price outside BB + RSI extreme + in best hour = fade the move

        if not pos or pos.qty == 0:
            # LONG setup: price below lower band + RSI oversold
            if current_close < lower_band and rsi is not None and rsi < self.rsi_oversold and in_best_hour:
                stop_price = round(current_close - self.atr_multiplier * atr, 2)
                target_price = round(min(
                    current_close + self.profit_target_atr * atr,
                    self.resistance_level * 0.998  # stay slightly below resistance
                ), 2)
                qty = self.max_position

                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "LIMIT",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar = current_bar_idx
                print(f"[MR] LONG entry @ {current_close} | BB lower={round(lower_band,2)} | RSI={round(rsi,1)} | Stop={stop_price} | Target={target_price}")

            # SHORT setup: price above upper band + RSI overbought
            elif current_close > upper_band and rsi is not None and rsi > self.rsi_overbought and in_best_hour:
                stop_price = round(current_close + self.atr_multiplier * atr, 2)
                target_price = round(current_close - self.profit_target_atr * atr, 2)
                qty = self.max_position

                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "LIMIT",
                    "price": round(current_close, 2),
                    "qty": qty,
                })
                self.last_trade_bar = current_bar_idx
                print(f"[MR] SHORT entry @ {current_close} | BB upper={round(upper_band,2)} | RSI={round(rsi,1)} | Stop={stop_price} | Target={target_price}")

        else:
            # ── Exit Logic ──
            # Exit long: hit resistance or price back to SMA (mean reversion complete)
            if pos.qty > 0:
                if current_close >= self.resistance_level * 0.995 or current_close >= sma:
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "LIMIT",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    print(f"[MR] LONG exit @ {current_close} | Resistance/SMA reached")

            # Exit short: price back to SMA
            elif pos.qty < 0:
                if current_close <= sma:
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "LIMIT",
                        "price": round(current_close, 2),
                        "qty": abs(pos.qty),
                    })
                    print(f"[MR] SHORT exit @ {current_close} | SMA reached")

        # Filter zero-qty orders
        return [o for o in orders if o.get("qty", 0) > 0]
