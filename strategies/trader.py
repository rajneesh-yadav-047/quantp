class Strategy:
    def __init__(self):
        self.name = "EMA Crossover Template"
        self.ema_fast = 9
        self.ema_slow = 21

    def on_bar(self, state):
        orders = []
        
        # Loop through all symbols in current market state
        for symbol, candles in state.historical_candles.items():
            # Ensure we have enough data to calculate the moving averages
            if len(candles) < self.ema_slow:
                continue

            # Extract close prices
            closes = [c.close for c in candles]
            
            # Compute exponential moving averages using pandas (allowed inside sandbox)
            import pandas as pd
            series = pd.Series(closes)
            ema_f = series.ewm(span=self.ema_fast, adjust=False).mean().iloc[-1]
            ema_s = series.ewm(span=self.ema_slow, adjust=False).mean().iloc[-1]
            
            # Check current position size
            current_position = state.positions.get(symbol)
            qty = current_position.qty if current_position else 0
            
            # Crossover logic
            if ema_f > ema_s and qty <= 0:
                # Buy trigger (reverse short or buy fresh)
                order_qty = 10 if qty == 0 else 20
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": order_qty
                })
                print(f"[{state.current_time}] BUY SIGNAL: Fast EMA {ema_f:.2f} > Slow EMA {ema_s:.2f}. Ordering {order_qty} units.")
                
            elif ema_f < ema_s and qty >= 0:
                # Sell trigger (reverse long or sell fresh)
                order_qty = 10 if qty == 0 else 20
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": order_qty
                })
                print(f"[{state.current_time}] SELL SIGNAL: Fast EMA {ema_f:.2f} < Slow EMA {ema_s:.2f}. Ordering {order_qty} units.")
                
        return orders
