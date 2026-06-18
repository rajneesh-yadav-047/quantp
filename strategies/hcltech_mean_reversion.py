"""
Mean Reversion Strategy for HCLTECH (5-Min)
============================================

Research Diagnosis:
  Symbol:        NSE:HCLTECH-EQ
  Interval:      FIVE_MINUTE
  Trend:         NEUTRAL
  Vol Regime:    LOW
  Body/Range:    0.425 (indecision candles — low conviction)
  Sharpe:        -0.09 (flat — no trend edge)
  Skewness:      -0.743 (negative tail — big down moves)
  ADX:           16.91 (no trend)
  R-squared:     0.0473 (price is not trend-following)
  Autocorr:      0.028 (no momentum)
  Ranging Regime: 59.5% combined (QUIET + VOLATILE ranging)
  Best Hour:     10:00 AM (strongest edge)
  Support:       1123.78
  Resistance:    1170.87

Why Mean Reversion?
  The research engine recommends mean_reversion with score 100/100.
  This is a textbook ranging stock: no trend, low volatility, indecision candles,
  and price oscillates around a mean. The strategy fades extremes and captures
  the reversion to the middle.

Risk Control:
  - Negative skewness means big down moves happen. Use a tight stop.
  - Only trade during the 10 AM power hour (strongest edge).
  - Don't short aggressively — the left tail is dangerous.
  - Keep position size small for low-volatility instrument.

Runtime:   legacy_on_bar
Symbols:   ["NSE:HCLTECH-EQ"]
Interval:  FIVE_MINUTE
"""

class Strategy:
    def __init__(self):
        self.bb_period = 20
        self.bb_std = 2.0
        self.trade_hour = 10          # Best hour from research: 10 AM
        self.max_position = 10        # Small size for low-volatility stock
        self.stop_loss_pct = 0.50     # Tight stop given negative skewness
        self.take_profit_pct = 0.80   # Slightly wider target for reversion
        self.min_closes = 25          # Need at least 25 bars for reliable bands

        self.closes = []              # Rolling close-price history
        self.entry_price = 0.0        # Track entry for stop/target
        self.has_position = False

    def on_bar(self, state):
        """
        Called every 5-minute candle tick.

        Returns: list of order dicts
        """
        symbol = "NSE:HCLTECH-EQ"
        candle = state.current_candle.get(symbol)
        if candle is None:
            return []

        # ── 1. Time Filter — Only trade during 10:00-10:59 AM ──────
        current_time = state.current_time
        try:
            hour = int(current_time[11:13])  # Extract HH from "YYYY-MM-DD HH:MM:SS"
        except (IndexError, ValueError):
            hour = 0

        if hour != self.trade_hour:
            return []  # No trades outside the best hour

        # ── 2. Build Price History ───────────────────────────────────
        hist = state.historical_candles.get(symbol, [])
        self.closes = [c.close for c in hist] + [candle.close]
        if len(self.closes) < self.min_closes:
            return []  # Not enough data yet

        # ── 3. Compute Bollinger Bands ───────────────────────────────
        sma = sum(self.closes[-self.bb_period:]) / self.bb_period
        variance = sum((c - sma) ** 2 for c in self.closes[-self.bb_period:]) / self.bb_period
        std = variance ** 0.5
        upper_band = sma + self.bb_std * std
        lower_band = sma - self.bb_std * std
        close = candle.close

        # ── 4. Position Check ────────────────────────────────────────
        pos = state.positions.get(symbol)
        current_qty = pos.qty if pos else 0

        orders = []

        # ── 5. Exit Logic (stop loss / take profit) ────────────────
        if current_qty != 0 and self.entry_price > 0:
            pnl_pct = ((close - self.entry_price) / self.entry_price) * 100.0

            # Long position: stop or target hit
            if current_qty > 0:
                if pnl_pct <= -self.stop_loss_pct:
                    # Stop loss — close long
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": 0.0,
                        "qty": current_qty,
                    })
                    self.has_position = False
                    self.entry_price = 0.0
                    return orders

                if pnl_pct >= self.take_profit_pct:
                    # Take profit — close long
                    orders.append({
                        "symbol": symbol,
                        "direction": "SELL",
                        "type": "MARKET",
                        "price": 0.0,
                        "qty": current_qty,
                    })
                    self.has_position = False
                    self.entry_price = 0.0
                    return orders

            # Short position: stop or target hit (avoid if possible — left tail risk)
            if current_qty < 0:
                if pnl_pct <= -self.stop_loss_pct:
                    # Stop loss — close short
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": 0.0,
                        "qty": abs(current_qty),
                    })
                    self.has_position = False
                    self.entry_price = 0.0
                    return orders

                if pnl_pct >= self.take_profit_pct:
                    # Take profit — close short
                    orders.append({
                        "symbol": symbol,
                        "direction": "BUY",
                        "type": "MARKET",
                        "price": 0.0,
                        "qty": abs(current_qty),
                    })
                    self.has_position = False
                    self.entry_price = 0.0
                    return orders

        # ── 6. Entry Logic — Mean Reversion ─────────────────────────
        # FADE EXTREMES: price below lower band = buy, price above upper band = sell
        # Given negative skewness, we are BULLISH-biased — prefer longs at support

        # LONG: Price touches or breaches lower band
        if close <= lower_band and current_qty <= 0:
            qty = self.max_position
            if current_qty < 0:
                # Flip short to long
                qty = abs(current_qty) + self.max_position
            orders.append({
                "symbol": symbol,
                "direction": "BUY",
                "type": "MARKET",
                "price": 0.0,
                "qty": qty,
            })
            self.entry_price = close
            self.has_position = True
            return orders

        # SHORT: Price touches or breaches upper band
        # DANGER: Negative skewness means left-tail risk. We only short when
        # price is clearly at resistance AND we are already long (flip position).
        if close >= upper_band and current_qty > 0:
            # Close the long and flip to short
            orders.append({
                "symbol": symbol,
                "direction": "SELL",
                "type": "MARKET",
                "price": 0.0,
                "qty": current_qty + self.max_position,
            })
            self.entry_price = close
            self.has_position = True
            return orders

        # ── 7. Mean Reversion at SMA ───────────────────────────────
        # If price crosses back to SMA while we have a position, take profit early
        # This captures the "reversion" part of mean reversion
        if self.has_position and abs(close - sma) < 0.3 * std:
            if current_qty > 0:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": current_qty,
                })
                self.has_position = False
                self.entry_price = 0.0
                return orders
            if current_qty < 0:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": abs(current_qty),
                })
                self.has_position = False
                self.entry_price = 0.0
                return orders

        return orders


# ═══════════════════════════════════════════════════════════════════════
#  HOW TO USE THIS STRATEGY
# ═══════════════════════════════════════════════════════════════════════
#  1. Save this as a strategy in the QuantLab Strategy Workspace
#  2. Set Runtime Type to: legacy_on_bar
#  3. Set Symbols to: ["NSE:HCLTECH-EQ"]
#  4. Set Interval to: FIVE_MINUTE
#  5. Set Initial Capital to: 100000
#  6. Set Max Position Size to: 10 (or match self.max_position)
#  7. Run backtest on the same date range as the research analysis
#  8. Check the Research Lab for regime attribution after the run
#
#  TUNABLE PARAMETERS:
#    bb_period      — 20 (try 15 for tighter, 25 for smoother)
#    bb_std         — 2.0 (try 1.5 for earlier signals, 2.5 for extreme only)
#    trade_hour     — 10 (the research-identified best hour)
#    stop_loss_pct  — 0.50 (tight given negative skewness)
#    take_profit_pct — 0.80 (wider to let mean reversion complete)
#    max_position   — 10 (small for low-volatility instrument)
# ═══════════════════════════════════════════════════════════════════════
