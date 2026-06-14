class Strategy:
    """
    Simple EMA Crossover - Single Symbol Strategy
    
    Uses the new on_bar(state) signature.
    The state object has:
      - state.current_candle: dict of {symbol: Candle} for the current tick
      - state.historical_candles: dict of {symbol: [Candle, ...]} for past candles
      - state.positions: dict of {symbol: Position} for current positions
      - state.portfolio: Portfolio with cash, equity, etc.
    
    The symbol key is in canonical form (e.g. "NSE:SBIN-EQ").
    """
    def __init__(self):
        self.fast_period = 9
        self.slow_period = 21
    
    def on_bar(self, state):
        orders = []
        
        for symbol, candle in state.current_candle.items():
            hist = state.historical_candles.get(symbol, [])
            all_candles = list(hist) + [candle]
            
            if len(all_candles) < self.slow_period + 1:
                continue
            
            closes = [c.close for c in all_candles]
            fast_ema = sum(closes[-self.fast_period:]) / self.fast_period
            slow_ema = sum(closes[-self.slow_period:]) / self.slow_period
            prev_fast = sum(closes[-self.fast_period - 1:-1]) / self.fast_period
            prev_slow = sum(closes[-self.slow_period - 1:-1]) / self.slow_period
            
            pos = state.positions.get(symbol)
            has_long = pos and pos.qty > 0
            has_short = pos and pos.qty < 0
            
            # Bullish crossover (fast crosses above slow)
            if prev_fast <= prev_slow and fast_ema > slow_ema and not has_long:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": 10
                })
            # Bearish crossover (fast crosses below slow)
            elif prev_fast >= prev_slow and fast_ema < slow_ema and not has_short:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": 10
                })
            
            # Close position if trend reverses
            if has_long and fast_ema < slow_ema:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": pos.qty
                })
            elif has_short and fast_ema > slow_ema:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": abs(pos.qty)
                })
        
        return orders
