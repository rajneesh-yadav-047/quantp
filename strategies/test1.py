class Strategy:

    def __init__(self):

        self.max_position = 10

        self.stop_loss_pct = 0.40
        self.take_profit_pct = 0.60

        self.min_closes = 25
        self.max_hold_bars = 12

        self.entry_price = 0.0
        self.hold_bars = 0

    def on_bar(self, state):

        symbol = "NSE:HCLTECH-EQ"

        candle = state.current_candle.get(symbol)
        if candle is None:
            return []

        close = candle.close

        hist = state.historical_candles.get(symbol, [])
        closes = [c.close for c in hist] + [close]

        if len(closes) < self.min_closes:
            return []

        sma20 = sum(closes[-20:]) / 20

        pos = state.positions.get(symbol)
        current_qty = pos.qty if pos else 0

        orders = []

        # ==================================================
        # EXIT LOGIC
        # ==================================================

        if current_qty > 0 and self.entry_price > 0:

            self.hold_bars += 1

            pnl_pct = (
                (close - self.entry_price)
                / self.entry_price
            ) * 100

            if pnl_pct <= -self.stop_loss_pct:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": current_qty
                })
                self._reset()
                return orders

            if pnl_pct >= self.take_profit_pct:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": current_qty
                })
                self._reset()
                return orders

            if close >= sma20:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": current_qty
                })
                self._reset()
                return orders

            if self.hold_bars >= self.max_hold_bars:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": current_qty
                })
                self._reset()
                return orders

        # ==================================================
        # ENTRY LOGIC
        # ==================================================

        if current_qty == 0:

            # Three-bar pullback
            red1 = closes[-2] < closes[-3]
            red2 = closes[-3] < closes[-4]

            # Price stretched below mean
            deviation = ((sma20 - close) / sma20) * 100

            if red1 and red2 and deviation > 0.30:

                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": self.max_position
                })

                self.entry_price = close
                self.hold_bars = 0

                return orders

        return orders

    def _reset(self):

        self.entry_price = 0.0
        self.hold_bars = 0