class Strategy:
    """
    QuantLab Market Maker v1.0
    ==========================
    A two-sided market making strategy that captures bid-ask spread
    while managing inventory risk.

    Key mechanics:
    1. Quotes LIMIT orders on both sides of the mid price every bar
    2. Spread width adapts to recent volatility (ATR-based)
    3. Inventory skew shifts the mid to encourage flattening
    4. Emergency MARKET flatten when inventory exceeds threshold
    5. Size scales down as inventory builds to limit one-sided risk

    Parameters you can tune in the IDE:
    - base_quote_size:  how many shares per quote (default 10)
    - max_inventory:    max absolute position before emergency flatten (default 100)
    - base_spread_bps:  base spread in basis points (default 5 = 0.05%)
    - vol_lookback:     bars to compute ATR for spread scaling (default 14)
    - skew_factor:      how aggressively to skew quotes (default 0.3)
    - flatten_pct:      inventory % that triggers emergency MARKET flatten (default 0.8)
    """

    def __init__(self):
        self.name = "Market Maker v1.0"
        self.base_quote_size = 1      # Shares per quote
        self.max_inventory = 100       # Max absolute position
        self.base_spread_bps = 5.0     # Base spread in basis points (0.05%)
        self.vol_lookback = 14         # ATR lookback period
        self.skew_factor = 0.3         # Inventory skew aggressiveness
        self.flatten_pct = 0.8         # Trigger emergency flatten at 80% of max_inventory

    def on_bar(self, state):
        """
        Called once per bar. Returns a list of order dicts.
        """
        orders = []

        for symbol, candle in state.current_candle.items():
            close = float(candle.close)
            high = float(candle.high)
            low = float(candle.low)
            
            # --- Current inventory ---
            pos = state.positions.get(symbol)
            inventory = pos.qty if pos else 0
            
            # --- Recent volatility (ATR-style) for dynamic spread ---
            hist = state.historical_candles.get(symbol, [])
            atr = self._compute_atr(hist, self.vol_lookback)
            
            # Spread = base_spread + volatility premium
            # If ATR is high relative to close, widen the spread
            vol_pct = (atr / close) * 100 if close > 0 else 0
            spread_bps = self.base_spread_bps + (vol_pct * 100)  # convert to bps
            spread_bps = max(spread_bps, 2.0)  # minimum 2 bps spread
            spread = spread_bps / 10000.0  # convert bps -> decimal
            
            # --- Inventory skew ---
            # Shift mid price to make the side we need more aggressive.
            # If we're long (inventory > 0), raise mid so asks get tighter
            # and bids get wider — encourages selling.
            inventory_ratio = inventory / self.max_inventory if self.max_inventory else 0
            skew = close * spread * self.skew_factor * inventory_ratio
            mid = close + skew
            
            bid_price = mid * (1 - spread)
            ask_price = mid * (1 + spread)
            
            # Round to 2 decimals (Indian equity tick size)
            bid_price = round(bid_price, 2)
            ask_price = round(ask_price, 2)
            
            # --- Size scaling ---
            # Reduce quote size as inventory builds to avoid over-exposure
            buy_size = max(1, int(self.base_quote_size * (1 - max(0, inventory_ratio))))
            sell_size = max(1, int(self.base_quote_size * (1 - max(0, -inventory_ratio))))
            
            # --- Place BUY LIMIT (bid) ---
            if inventory < self.max_inventory and bid_price < close:
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "LIMIT",
                    "price": bid_price,
                    "qty": buy_size,
                })
            
            # --- Place SELL LIMIT (ask) ---
            if inventory > -self.max_inventory and ask_price > close:
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "LIMIT",
                    "price": ask_price,
                    "qty": sell_size,
                })
            
            # --- Emergency flatten ---
            # If inventory exceeds flatten_pct of max, use MARKET order
            # to aggressively reduce exposure
            if abs(inventory) >= self.max_inventory * self.flatten_pct:
                flatten_dir = "SELL" if inventory > 0 else "BUY"
                flatten_qty = max(1, abs(inventory) // 2)
                orders.append({
                    "symbol": symbol,
                    "direction": flatten_dir,
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": flatten_qty,
                })
                print(f"[MM] EMERGENCY FLATTEN: {flatten_dir} {flatten_qty} {symbol} @ {state.current_time} | inventory={inventory}")
            
            # --- Debug logging ---
            print(f"[MM] {symbol} @ {state.current_time} | close={close:.2f} mid={mid:.2f} "
                  f"bid={bid_price:.2f} ask={ask_price:.2f} spread={spread_bps:.1f}bps "
                  f"inv={inventory} buy_sz={buy_size} sell_sz={sell_size}")

        return orders

    def _compute_atr(self, candles, lookback):
        """
        Compute Average True Range from recent candles.
        Returns absolute ATR value (not percentage).
        """
        if len(candles) < 2:
            return 0.0
        
        # Use last N candles
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
        
        # Simple moving average of TR
        return sum(tr_values) / len(tr_values)
