# How to Run Multi-Symbol Backtests in QuantLab

## Step 1: Create the Strategy in the UI

1. Open the app at **http://localhost:3000**
2. Go to the **Strategies** tab
3. Click the **New Strategy** button (plus icon on the left sidebar)
4. Fill in the form:
   - **Strategy Name**: `Multi-Symbol RSI Strategy`
   - **Symbols**: `SBIN, RELIANCE, TATAMOTORS` (comma-separated, bare symbols are fine)
   - **Interval**: `FIVE_MINUTE` (or whatever you want)
   - **Initial Capital**: `100000`
   - **Max Position Size**: `5` (per symbol)
   - **Runtime Type**: `Legacy On-Bar` (default)
   - **Entrypoint**: leave blank
5. Click **Upload .py file** and select `strategies/multi_rsi_mean_reversion.py`
6. Click **Save to Database**

## Step 2: Run the Backtest

1. Go to the **Backtests** tab
2. Select your strategy from the dropdown
3. Set the **date range** (must be within the data you have downloaded)
   - For example: `2026-06-08` to `2026-06-12`
4. Click **Run Backtest**
5. The engine will:
   - Load data for **all three symbols** simultaneously
   - Feed each symbol's candle into `state.current_candle` and `state.historical_candles`
   - The strategy loops through every symbol and places orders per symbol
   - You get a single equity curve combining all symbols

## What the Engine Does Internally

The `BacktestEngine` receives a `df_dict` like this:
```python
{
    "NSE:SBIN-EQ": DataFrame(...),
    "NSE:RELIANCE-EQ": DataFrame(...),
    "NSE:TATAMOTORS-EQ": DataFrame(...)
}
```

At each time step, it builds a `MarketState` with:
```python
state.current_candle = {
    "NSE:SBIN-EQ": Candle(open=..., high=..., low=..., close=...),
    "NSE:RELIANCE-EQ": Candle(...),
    ...
}

state.historical_candles = {
    "NSE:SBIN-EQ": [Candle, Candle, ...],
    "NSE:RELIANCE-EQ": [Candle, Candle, ...],
    ...
}

state.positions = {
    "NSE:SBIN-EQ": Position(qty=10, avg_price=...),
    ...
}
```

Your strategy should loop through `state.current_candle.items()` and return orders for each symbol.

## Tips for Multi-Symbol Strategies

1. **Symbol keys are canonical** — use the exact key from the dict (e.g. `NSE:SBIN-EQ`), not bare `SBIN`
2. **Check `len(hist)` before using history** — some symbols may start at different times
3. **Use `state.positions`** to track per-symbol holdings and avoid over-trading
4. **Qty is per-symbol** — each symbol trades independently; the total position is the sum across all symbols
5. **The equity curve is combined** — one backtest = one portfolio across all symbols

## Quick Test via API (curl)

```bash
# Create the strategy
curl -s -X POST http://localhost:8000/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Multi RSI",
    "description": "",
    "code": "class Strategy:\n    def __init__(self):\n        self.period = 14\n        self.oversold = 30\n        self.overbought = 70\n        self.qty_per_symbol = 5\n    def on_bar(self, state):\n        orders = []\n        for symbol, candle in state.current_candle.items():\n            hist = state.historical_candles.get(symbol, [])\n            all_candles = list(hist) + [candle]\n            if len(all_candles) < self.period + 1:\n                continue\n            closes = [c.close for c in all_candles]\n            gains, losses = [], []\n            for i in range(1, len(closes)):\n                delta = closes[i] - closes[i-1]\n                if delta > 0:\n                    gains.append(delta); losses.append(0)\n                else:\n                    gains.append(0); losses.append(abs(delta))\n            avg_gain = sum(gains[-self.period:]) / self.period\n            avg_loss = sum(losses[-self.period:]) / self.period\n            rsi = 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))\n            pos = state.positions.get(symbol)\n            has_long = pos and pos.qty > 0\n            has_short = pos and pos.qty < 0\n            if rsi < self.oversold and not has_long:\n                orders.append({\"symbol\": symbol, \"direction\": \"BUY\", \"type\": \"MARKET\", \"price\": 0.0, \"qty\": self.qty_per_symbol})\n            elif rsi > self.overbought and not has_short:\n                orders.append({\"symbol\": symbol, \"direction\": \"SELL\", \"type\": \"MARKET\", \"price\": 0.0, \"qty\": self.qty_per_symbol})\n            if has_long and rsi > 50:\n                orders.append({\"symbol\": symbol, \"direction\": \"SELL\", \"type\": \"MARKET\", \"price\": 0.0, \"qty\": pos.qty})\n            elif has_short and rsi < 50:\n                orders.append({\"symbol\": symbol, \"direction\": \"BUY\", \"type\": \"MARKET\", \"price\": 0.0, \"qty\": abs(pos.qty)})\n        return orders\n",
    "symbols": ["SBIN", "RELIANCE", "TATAMOTORS"],
    "interval": "FIVE_MINUTE",
    "initial_capital": 100000,
    "max_position_size": 5,
    "runtime_type": "legacy_on_bar"
  }'

# Run backtest (replace STRATEGY_ID with the id from above)
curl -s -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "STRATEGY_ID",
    "symbols": ["SBIN", "RELIANCE", "TATAMOTORS"],
    "interval": "FIVE_MINUTE",
    "start_date": "2026-06-08",
    "end_date": "2026-06-12",
    "initial_capital": 100000,
    "slippage_pct": 0.0005,
    "trade_type": "INTRADAY",
    "max_position_size": 5,
    "auto_download": true
  }'
```
