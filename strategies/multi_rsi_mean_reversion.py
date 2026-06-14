class Strategy:
    """
    Multi-Symbol RSI Mean Reversion Strategy

    Runs the same signal on ALL symbols in the backtest simultaneously.

    How to use for multi-symbol backtests:
    1. In the Strategies tab, set Symbols to multiple symbols (e.g. "SBIN, RELIANCE, TATAMOTORS")
    2. Save the strategy
    3. Go to Backtests tab, select the strategy, pick a date range, and hit Run
    4. The engine will load data for ALL symbols and feed them to this strategy

    The state object gives you one candle per symbol at each step.
    The symbol key is the canonical form (e.g. "NSE:SBIN-EQ").
    """
    def __init__(self):
        self.period = 14
        self.oversold = 30
        self.overbought = 70
        self.qty_per_symbol = 5

    def on_bar(self, state):
        orders = []

        for symbol, candle in state.current_candle.items():
            hist = state.historical_candles.get(symbol, [])
            all_candles = list(hist) + [candle]

            if len(all_candles) < self.period + 1:
                continue

            # Simple RSI approximation
            closes = [c.close for c in all_candles]
            gains = []
            losses = []
            for i in range(1, len(closes)):
                delta = closes[i] - closes[i - 1]
                if delta > 0:
                    gains.append(delta)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(delta))

            avg_gain = sum(gains[-self.period:]) / self.period
            avg_loss = sum(losses[-self.period:]) / self.period
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            pos = state.positions.get(symbol)
            has_long = pos and pos.qty > 0
            has_short = pos and pos.qty < 0

            # Oversold -> Buy (mean reversion, expect bounce up)
            if rsi < self.oversold and not has_long:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": self.qty_per_symbol
                })
            # Overbought -> Sell (mean reversion, expect pullback)
            elif rsi > self.overbought and not has_short:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": self.qty_per_symbol
                })

            # Exit on mean reversion (RSI returns to neutral zone)
            if has_long and rsi > 50:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": pos.qty
                })
            elif has_short and rsi < 50:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": abs(pos.qty)
                })

        return orders
