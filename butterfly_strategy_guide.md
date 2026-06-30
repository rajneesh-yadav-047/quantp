# Long Call Butterfly Strategy — Backtest Guide

This is a **neutral-to-bullish, low-risk, limited-reward** options strategy. You buy a lower-strike call, sell two middle-strike calls, and buy a higher-strike call. All legs share the same expiry.

---

## 1. Strategy Code

Save this as a strategy file (or paste it via `POST /api/strategies`). The strategy runtime emits `instrument_type="OPTION"` orders, which the backtester now routes through the options execution pipeline.

```python
"""
Long Call Butterfly (NIFTY 50)
- Buy 1x CE  at  strike - 50  (lower wing)
- Sell 2x CE  at  strike       (body)
- Buy 1x CE  at  strike + 50  (higher wing)

Entry: 09:20 (give market 5 minutes to settle)
Exit:  15:15 (square off before closing volatility)
"""

from engine.runtime.datamodels import Order, TradingState

# Butterfly configuration
UNDERLYING = "NIFTY"
STRIKE     = 24500       # ATM strike — adjust to current spot
EXPIRY     = "2025-07-03"  # Weekly expiry date
LOT_SIZE   = 75

def on_tick(state: TradingState):
    orders = []
    t = state.timestamp
    time_only = t[11:16]

    # Entry at 09:20
    if time_only == "09:20":
        orders.append(Order(
            symbol=UNDERLYING,
            direction="BUY",
            type="MARKET",
            price=0.0,
            quantity=1,
            instrument_type="OPTION",
            expiry=EXPIRY,
            strike=STRIKE - 50,
            option_type="CE",
            action="BUY",
            quantity_lots=1,
        ))
        orders.append(Order(
            symbol=UNDERLYING,
            direction="SELL",
            type="MARKET",
            price=0.0,
            quantity=2,
            instrument_type="OPTION",
            expiry=EXPIRY,
            strike=STRIKE,
            option_type="CE",
            action="SELL",
            quantity_lots=2,
        ))
        orders.append(Order(
            symbol=UNDERLYING,
            direction="BUY",
            type="MARKET",
            price=0.0,
            quantity=1,
            instrument_type="OPTION",
            expiry=EXPIRY,
            strike=STRIKE + 50,
            option_type="CE",
            action="BUY",
            quantity_lots=1,
        ))

    # Square off at 15:15
    if time_only == "15:15":
        # Reverse all legs with opposite action
        orders.append(Order(
            symbol=UNDERLYING,
            direction="SELL",
            type="MARKET",
            price=0.0,
            quantity=1,
            instrument_type="OPTION",
            expiry=EXPIRY,
            strike=STRIKE - 50,
            option_type="CE",
            action="SELL",
            quantity_lots=1,
        ))
        orders.append(Order(
            symbol=UNDERLYING,
            direction="BUY",
            type="MARKET",
            price=0.0,
            quantity=2,
            instrument_type="OPTION",
            expiry=EXPIRY,
            strike=STRIKE,
            option_type="CE",
            action="BUY",
            quantity_lots=2,
        ))
        orders.append(Order(
            symbol=UNDERLYING,
            direction="SELL",
            type="MARKET",
            price=0.0,
            quantity=1,
            instrument_type="OPTION",
            expiry=EXPIRY,
            strike=STRIKE + 50,
            option_type="CE",
            action="SELL",
            quantity_lots=1,
        ))

    return orders, "{}"
```

---

## 2. Backtest Steps

### Step 1 — Download the Underlying Equity Data

The backtester needs the underlying NIFTY spot candles to:
- Align timestamps across the simulation
- Determine ITM/OTM for expiry-day auto-exercise STT

```bash
POST http://localhost:8000/api/data/download
Content-Type: application/json

{
  "symbol": "NSE:NIFTY 50",
  "interval": "ONE_MINUTE",
  "from_date": "2025-06-23",
  "to_date": "2025-06-27",
  "totp": "<your-otp>"
}
```

*(Or use `FIVE_MINUTE` if you prefer less granular data. The backtester will still align timestamps.)*

### Step 2 — Download the 3 Option Legs

Use the new options download endpoint to fetch the 1-minute OHLC for each strike.

```bash
POST http://localhost:8000/api/options/download
Content-Type: application/json

{
  "symbol": "NIFTY",
  "expiry": "2025-07-03",
  "strikes": [24450, 24500, 24550],
  "option_types": ["CE"],
  "from_dt": "2025-06-23 09:15",
  "to_dt": "2025-06-27 15:30"
}
```

This queues a background job. Poll for status:

```bash
GET http://localhost:8000/api/data/download/jobs/{job_id}
```

Repeat for every expiry week you want to backtest. The parquet files land at:

```
datasets/options/NFO/NIFTY/2025-07-03/24450_CE.parquet
datasets/options/NFO/NIFTY/2025-07-03/24500_CE.parquet
datasets/options/NFO/NIFTY/2025-07-03/24550_CE.parquet
```

### Step 3 — Create the Strategy in the Database

```bash
POST http://localhost:8000/api/strategies
Content-Type: application/json

{
  "name": "Long Call Butterfly NIFTY",
  "code": "<paste the strategy code above>",
  "symbols": ["NIFTY"],
  "interval": "ONE_MINUTE",
  "initial_capital": 500000,
  "max_position_size": 10
}
```

Save the returned `id` — this is your `strategy_id`.

### Step 4 — Run the Backtest

```bash
POST http://localhost:8000/api/backtest/run
Content-Type: application/json

{
  "strategy_id": "<strategy-id-from-step-3>",
  "symbol": "NIFTY",
  "interval": "ONE_MINUTE",
  "start_date": "2025-06-23",
  "end_date": "2025-06-27",
  "initial_capital": 500000,
  "slippage_pct": 0.0005,
  "trade_type": "OPTIONS"
}
```

The backtester will:
1. Load the underlying NIFTY equity dataframe
2. When the strategy emits `instrument_type="OPTION"` orders at 09:20, it will:
   - Resolve tokens via `options_catalog.resolve_token`
   - Read the 1-minute premium from the parquet file
   - Apply `options_slippage_pct` (1% default) to the fill price
   - Call `calculate_options_charges` with correct option STT, GST, exchange charges, stamp duty
3. On 15:15, square off the legs with reversed actions and the same charge math
4. If expiry day falls in the range, at 15:25 it will:
   - Compare NIFTY spot to each strike to determine ITM/OTM
   - Apply `0.00125 × strike × lot_size × qty` auto-exercise STT if ITM
   - Close the position at the last available candle premium
5. Return the standard equity-curve and trade-log JSON (with new `instrument_type`, `strike`, `option_type`, `expiry`, `charges_breakdown` fields on each trade)

### Step 5 — Inspect Results

```bash
GET http://localhost:8000/api/backtest/results/{run_id}
```

The response contains:
- `trades[]` with `instrument_type: "OPTION"` and full `charges_breakdown`
- `equity_curve[]` with P&L inclusive of option-specific charges
- `final_portfolio` summary

---

## 3. Alternative: Using the Visual Strategy Builder

If you prefer the UI (Axon frontend → Options Studio):

1. Go to **Options Studio** → Create strategy
2. Select template: **Custom Butterfly**
3. Set underlying: `NIFTY 50`
4. Set expiry type: `WEEKLY`
5. Add legs:
   - Leg 0: BUY 1 CE at `ATM-50`
   - Leg 1: SELL 2 CE at `ATM`
   - Leg 2: BUY 1 CE at `ATM+50`
6. Set entry time `09:20`, exit time `15:15`
7. Save → the system auto-generates the Python code and creates a `StrategyDB` entry
8. Go to **Backtest** tab, select the strategy, set date range, and run

---

## 4. Pro Tip: Bulk Historical Data via NSE Bhavcopy

If you want years of EOD options history **without SmartAPI credits**:

```bash
POST http://localhost:8000/api/options/import-bhavcopy
Content-Type: application/json

{
  "from_date": "2024-01-01",
  "to_date": "2025-06-27"
}
```

This downloads the free NSE F&O UDiFF bhavcopy archives, unzips them, and writes `ONE_DAY` interval parquet files into the same `datasets/options/NFO/...` tree. You can then backtest on daily bars without any API key.
