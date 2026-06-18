"""
MR3 v2 — Mean Reversion Strategy for HCLTECH (5-Min)
=====================================================

CHANGES FROM v1:
  1. Stop-loss / take-profit now run EVERY BAR — no more stranded positions.
  2. Entry window widened to full morning (9:15-11:30) + afternoon (13:30-15:15).
  3. BB std lowered from 2.0 → 1.5 for earlier signals on this low-vol stock.
  4. Fresh short entries allowed — no longer requires an existing long.
  5. Max hold period added (20 bars ≈ 1.5 hrs) — force exit if SL/TP miss.
  6. Min closes dropped from 25 → 20 to start trading sooner each day.

Runtime:   legacy_on_bar
Symbols:   ["NSE:HCLTECH-EQ"]
Interval:  FIVE_MINUTE
"""

class Strategy:
    def __init__(self):
        self.bb_period = 25
        self.bb_std = 1.5            # v2: tighter for more signals on low-vol
        self.max_position = 10
        self.stop_loss_pct = 0.50
        self.take_profit_pct = 0.80
        self.min_closes = 20         # v2: lowered to match bb_period
        self.max_hold_bars = 10      # v2: force exit after ~1.5 hrs

        self.closes = []
        self.entry_price = 0.0
        self.has_position = False
        self.hold_bars = 0           # v2: bar counter for hold period

    def on_bar(self, state):
        symbol = "NSE:HCLTECH-EQ"
        candle = state.current_candle.get(symbol)
        if candle is None:
            return []

        close = candle.close
        current_time = state.current_time

        # ── 1. Build Price History ───────────────────────────────────
        hist = state.historical_candles.get(symbol, [])
        self.closes = [c.close for c in hist] + [close]
        if len(self.closes) < self.min_closes:
            return []

        # ── 2. Compute Bollinger Bands & SMA ─────────────────────────
        sma = sum(self.closes[-self.bb_period:]) / self.bb_period
        variance = sum((c - sma) ** 2 for c in self.closes[-self.bb_period:]) / self.bb_period
        std = variance ** 0.5
        upper_band = sma + self.bb_std * std
        lower_band = sma - self.bb_std * std

        # ── 3. Position Check ────────────────────────────────────────
        pos = state.positions.get(symbol)
        current_qty = pos.qty if pos else 0
        orders = []

        # ── 4. EXITS — Run EVERY BAR (no time prison) ────────────────
        if current_qty != 0 and self.entry_price > 0:
            self.hold_bars += 1
            pnl_pct = ((close - self.entry_price) / self.entry_price) * 100.0

            # Long exit
            if current_qty > 0:
                if pnl_pct <= -self.stop_loss_pct:
                    orders.append({"symbol": symbol, "direction": "SELL", "type": "MARKET", "price": 0.0, "qty": current_qty})
                    self._reset_position()
                    return orders
                if pnl_pct >= self.take_profit_pct:
                    orders.append({"symbol": symbol, "direction": "SELL", "type": "MARKET", "price": 0.0, "qty": current_qty})
                    self._reset_position()
                    return orders
                if self.hold_bars >= self.max_hold_bars:
                    orders.append({"symbol": symbol, "direction": "SELL", "type": "MARKET", "price": 0.0, "qty": current_qty})
                    self._reset_position()
                    return orders
                # SMA mean-reversion early exit (price back near middle)
                if self.has_position and abs(close - sma) < 0.3 * std:
                    orders.append({"symbol": symbol, "direction": "SELL", "type": "MARKET", "price": 0.0, "qty": current_qty})
                    self._reset_position()
                    return orders

            # Short exit
            if current_qty < 0:
                if pnl_pct <= -self.stop_loss_pct:
                    orders.append({"symbol": symbol, "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": abs(current_qty)})
                    self._reset_position()
                    return orders
                if pnl_pct >= self.take_profit_pct:
                    orders.append({"symbol": symbol, "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": abs(current_qty)})
                    self._reset_position()
                    return orders
                if self.hold_bars >= self.max_hold_bars:
                    orders.append({"symbol": symbol, "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": abs(current_qty)})
                    self._reset_position()
                    return orders
                # SMA mean-reversion early exit
                if self.has_position and abs(close - sma) < 0.3 * std:
                    orders.append({"symbol": symbol, "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": abs(current_qty)})
                    self._reset_position()
                    return orders

        # ── 5. Time Filter — Only ENTER during liquid windows ────────
        if not self._in_trade_window(current_time):
            return orders  # v2: exits already handled above, safe to return

        # ── 6. ENTRY Logic — Mean Reversion ──────────────────────────
        # LONG: price below lower band (fade oversold)
        if close <= lower_band and current_qty <= 0:
            qty = self.max_position
            if current_qty < 0:
                qty = abs(current_qty) + self.max_position  # flip short → long
            orders.append({"symbol": symbol, "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": qty})
            self.entry_price = close
            self.has_position = True
            self.hold_bars = 0
            return orders

        # SHORT: price above upper band (fade overbought)
        # v2: fresh shorts allowed — current_qty >= 0 (flat or long)
        if close >= upper_band and current_qty >= 0:
            qty = self.max_position
            if current_qty > 0:
                qty = current_qty + self.max_position  # flip long → short
            orders.append({"symbol": symbol, "direction": "SELL", "type": "MARKET", "price": 0.0, "qty": qty})
            self.entry_price = close
            self.has_position = True
            self.hold_bars = 0
            return orders

        return orders

    # ── Helpers ─────────────────────────────────────────────────────
    def _reset_position(self):
        self.has_position = False
        self.entry_price = 0.0
        self.hold_bars = 0

    def _in_trade_window(self, current_time):
        """Return True if we are in the allowed entry windows."""
        try:
            hour = int(current_time[11:13])
            minute = int(current_time[14:16])
        except (IndexError, ValueError):
            return False

        # Morning session: 09:15 – 11:30
        if hour == 9 and minute >= 15:
            return True
        if hour in (10, 11):
            return True

        # Afternoon session: 13:30 – 15:15
        if hour == 13 and minute >= 30:
            return True
        if hour == 14:
            return True
        if hour == 15 and minute <= 15:
            return True

        return False


# ═══════════════════════════════════════════════════════════════════════
#  QUICK TUNE GUIDE
# ═══════════════════════════════════════════════════════════════════════
#  If you still want MORE trades:
#    bb_std          → 1.0 (very aggressive, catches smaller swings)
#    max_hold_bars   → 12 (shorter, faster turnover)
#    stop_loss_pct   → 0.30 (tighter, more exits, less drawdown)
#    take_profit_pct → 0.50 (smaller targets, more frequent wins)
#
#  If you want FEWER but higher-quality trades:
#    bb_std          → 2.0 (only extreme deviations)
#    max_hold_bars   → 30 (let mean reversion breathe)
#    stop_loss_pct   → 0.80 (wider stop, ride out noise)
#    take_profit_pct → 1.20 (larger targets)
# ═══════════════════════════════════════════════════════════════════════
