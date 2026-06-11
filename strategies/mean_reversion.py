class Strategy:
    """
    QuantLab Mean Reversion v1.0
    ==============================
    A statistical mean-reversion strategy that trades price deviations
    from a rolling Simple Moving Average (SMA), confirmed by RSI.

    Key mechanics:
    1. Computes SMA and Bollinger Bands (SMA ± k·σ) from recent bars
    2. Enters LONG when price drops below lower band + RSI oversold
    3. Enters SHORT when price rises above upper band + RSI overbought
    4. Exits when price reverts back toward the SMA (mean reversion)
    5. Position size scales inversely with volatility (ATR-based)
    6. Hard stop-loss at N×ATR to cap tail-risk

    Parameters you can tune in the IDE:
    - sma_period:       lookback for SMA / band centre (default 20)
    - std_mult:         Bollinger band width multiplier (default 2.0)
    - rsi_period:       RSI lookback (default 14)
    - rsi_oversold:     RSI threshold for long entry (default 30)
    - rsi_overbought:   RSI threshold for short entry (default 70)
    - max_position:     max absolute shares per symbol (default 100)
    - risk_per_trade:   % of equity risked per trade (default 2.0)
    - atr_lookback:     ATR lookback for sizing & stop (default 14)
    - stop_atr_mult:    stop-loss distance as multiple of ATR (default 2.0)
    """

    def __init__(self):
        self.name = "Mean Reversion v1.0"
        self.sma_period = 20
        self.std_mult = 2.0
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.max_position = 100
        self.risk_per_trade = 2.0
        self.atr_lookback = 14
        self.stop_atr_mult = 2.0

    def on_bar(self, state):
        """
        Called once per bar. Returns a list of order dicts.
        """
        orders = []

        for symbol, candle in state.current_candle.items():
            close = float(candle.close)
            high = float(candle.high)
            low = float(candle.low)
            open_p = float(candle.open)

            # --- Current inventory ---
            pos = state.positions.get(symbol)
            inventory = pos.qty if pos else 0

            # --- Historical candles ---
            hist = state.historical_candles.get(symbol, [])
            if len(hist) < self.sma_period:
                # Not enough history yet — skip
                continue

            # --- Compute SMA & StdDev ---
            recent_closes = [float(c.close) for c in hist[-self.sma_period:]]
            sma = sum(recent_closes) / len(recent_closes)
            variance = sum((c - sma) ** 2 for c in recent_closes) / len(recent_closes)
            std = variance ** 0.5

            upper_band = sma + self.std_mult * std
            lower_band = sma - self.std_mult * std

            # --- Compute RSI ---
            rsi = self._compute_rsi(hist, self.rsi_period)

            # --- Compute ATR for sizing & stops ---
            atr = self._compute_atr(hist, self.atr_lookback)

            # --- Position sizing (volatility-adjusted) ---
            equity = state.portfolio.equity if state.portfolio else 100000.0
            risk_amount = equity * (self.risk_per_trade / 100.0)
            stop_distance = atr * self.stop_atr_mult if atr > 0 else close * 0.02
            stop_distance = max(stop_distance, close * 0.005)  # min 0.5% stop
            size = int(risk_amount / stop_distance) if stop_distance > 0 else 1
            size = max(1, min(size, self.max_position))

            # --- Mean reversion signal logic ---
            # LONG:  price below lower band AND RSI oversold  → expect bounce up
            # SHORT: price above upper band AND RSI overbought → expect pullback
            long_signal = close < lower_band and (rsi is None or rsi < self.rsi_oversold)
            short_signal = close > upper_band and (rsi is None or rsi > self.rsi_overbought)

            # --- Exit logic: revert to mean ---
            # If long and price crosses back above SMA → take profit
            # If short and price crosses back below SMA → take profit
            long_exit = inventory > 0 and close > sma
            short_exit = inventory < 0 and close < sma

            # --- Emergency stop-loss (hard ATR-based) ---
            if pos and pos.avg_price > 0:
                long_stop_hit = inventory > 0 and close < (pos.avg_price - stop_distance)
                short_stop_hit = inventory < 0 and close > (pos.avg_price + stop_distance)
            else:
                long_stop_hit = False
                short_stop_hit = False

            # --- Place orders ---

            # ENTRY: LONG
            if long_signal and inventory <= 0:
                # Flat or short → go long
                target_qty = size if inventory == 0 else size + abs(inventory)
                target_qty = min(target_qty, self.max_position)
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "LIMIT",
                    "price": round(close, 2),
                    "qty": target_qty,
                })
                print(f"[MR] LONG ENTRY {symbol} @ {close:.2f} | sma={sma:.2f} band=[{lower_band:.2f},{upper_band:.2f}] rsi={rsi:.1f} sz={target_qty}")

            # ENTRY: SHORT
            elif short_signal and inventory >= 0:
                # Flat or long → go short
                target_qty = size if inventory == 0 else size + abs(inventory)
                target_qty = min(target_qty, self.max_position)
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "LIMIT",
                    "price": round(close, 2),
                    "qty": target_qty,
                })
                print(f"[MR] SHORT ENTRY {symbol} @ {close:.2f} | sma={sma:.2f} band=[{lower_band:.2f},{upper_band:.2f}] rsi={rsi:.1f} sz={target_qty}")

            # EXIT: Mean reversion complete (long)
            elif long_exit and not long_stop_hit:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "LIMIT",
                    "price": round(close, 2),
                    "qty": abs(inventory),
                })
                print(f"[MR] LONG EXIT {symbol} @ {close:.2f} | reverted to sma={sma:.2f} inv={inventory}")

            # EXIT: Mean reversion complete (short)
            elif short_exit and not short_stop_hit:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "LIMIT",
                    "price": round(close, 2),
                    "qty": abs(inventory),
                })
                print(f"[MR] SHORT EXIT {symbol} @ {close:.2f} | reverted to sma={sma:.2f} inv={inventory}")

            # STOP-LOSS: Long
            if long_stop_hit:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": abs(inventory),
                })
                print(f"[MR] STOP LOSS {symbol} @ {close:.2f} | long stop hit avg={pos.avg_price:.2f} dist={stop_distance:.2f}")

            # STOP-LOSS: Short
            if short_stop_hit:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": abs(inventory),
                })
                print(f"[MR] STOP LOSS {symbol} @ {close:.2f} | short stop hit avg={pos.avg_price:.2f} dist={stop_distance:.2f}")

            # --- Debug bar summary ---
            print(f"[MR] {symbol} @ {state.current_time} | close={close:.2f} sma={sma:.2f} "
                  f"bands=[{lower_band:.2f},{upper_band:.2f}] rsi={rsi:.1f} atr={atr:.2f} "
                  f"inv={inventory} size={size}")

        return orders

    def _compute_rsi(self, candles, period):
        """
        Compute Relative Strength Index from recent closes.
        Returns None if not enough data.
        """
        if len(candles) < period + 1:
            return None

        recent = candles[-(period + 1):]
        closes = [float(c.close) for c in recent]

        gains = 0.0
        losses = 0.0
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains += change
            else:
                losses += abs(change)

        avg_gain = gains / period
        avg_loss = losses / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def _compute_atr(self, candles, lookback):
        """
        Compute Average True Range from recent candles.
        Returns absolute ATR value.
        """
        if len(candles) < 2:
            return 0.0

        recent = candles[-lookback:] if len(candles) >= lookback else candles

        tr_values = []
        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]

            high = float(curr.high)
            low = float(curr.low)
            prev_close = float(prev.close)

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)

        if not tr_values:
            return 0.0

        return sum(tr_values) / len(tr_values)
