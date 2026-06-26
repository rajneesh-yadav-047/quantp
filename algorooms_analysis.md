# Algorooms vs QuantLab Feature Gap Analysis

## What Algorooms Is
Algorooms is a **visual no-code options strategy builder + backtesting platform** for Indian markets (NSE F&O). It connects to brokers (Angel One visible) and lets users build multi-leg options strategies without writing code, backtest them, and deploy live.

---

## Algorooms Feature Map (Screenshots Captured)

### 1. Navigation Sidebar
| Feature | Algorooms | QuantLab Status |
|---------|-----------|-----------------|
| Dashboard | ✅ Total P&L, broker card, strategy templates, deployment status | ✅ Partial (has dashboard but no strategy templates carousel) |
| Broker | ✅ Angel One integration, login status, Static IP, Terminal toggle, Trading Engine toggle | ✅ SmartAPI connected, but no Terminal/Engine toggles |
| Strategy Builder | ✅ **Visual no-code builder** for options (see below) | ❌ Only Python code editor |
| Strategies | ✅ My Strategies / Deployed Strategies / Strategy Templates tabs, search, Tradingview Signals Trading | ✅ Has strategies list, but no templates or TradingView signals |
| Backtesting | ✅ Strategy Backtest + **Simulator (Beta)** with live option chain | ✅ Has backtest engine with replay, but no option chain simulator |
| Reports | ✅ Report + Trade Engine Logs tabs, date range, broker filter, Live/Forward toggle, donut chart | ❌ Not present |
| Subscription | ✅ Subscription management | ❌ Not present |
| Wallet | ✅ Wallet icon in header | ❌ Not present |
| Dark Mode | ✅ Toggle in header | ❌ Not present |

### 2. Strategy Builder (The Big One)

Algorooms has a **3-panel visual builder** specifically for F&O:

**Panel 1 — Strategy Type**
- Option Trading-Time Based
- Option Trading-Indicator Based
- Stocks & Futures-Indicator Based

**Panel 2 — Select Instruments**
- Underlying: Spot / Future toggle
- + Add button to add multiple instruments

**Panel 3 — Strategy Legs** (the core feature)
- `+ Add Leg` button — build multi-leg strategies
- Each leg configures:
  - **Position**: BUY / SELL
  - **Option Type**: Call / Put
  - **Qty**: numeric input
  - **Multiples of lot**
  - **Expiry**: WEEKLY / dropdown
  - **Strike Criteria**: ATM pt / dropdown
  - **Strike Type**: ATM / dropdown
  - **SL Type**: SL% / dropdown
  - **SL**: numeric input
  - **On Price**: On Price / dropdown
  - **TP Type**: TP% / dropdown
  - **TP**: numeric input
  - **On Price**: On Price / dropdown
  - Delete / Copy icons per leg

**Order Type Section**
- MIS / CNC / BTST radio buttons
- Start Time picker (e.g., 09:16)
- Square Off time picker (e.g., 15:15)
- Day selection: MON TUE WED THU FRI toggle buttons

### 3. Simulator (Beta) — Live Option Chain

This is a **completely separate tool** from backtesting:
- **Live Option Chain** for NIFTY (or other underlyings)
- **Expiry selector**: 30 JUN 26, 07 JUL 26, 14 JUL 26, 21 JUL 26, etc.
- Columns: Call price, Delta, Strike, Delta, Put price
- **B/S buttons** (Buy/Sell) on every strike for quick position building
- **ATM indicator** on the chain
- **Right panel** shows:
  - EST. MARGIN
  - P&L
  - MAX PROFIT
  - MAX LOSS
  - POP (Probability of Profit)
  - NET PREMIUM
  - BREAKEVENS
- **Payoff visualization** graph (area chart style)
- "No positions added. Select strikes from Option Chain to visualize payoff"

### 4. Strategy Backtest
- Select Strategies dropdown (multi-select implied)
- Time range presets: **1 Month, 3 Months, 6 Months, 1 Year, 2 Years, Custom Range**
- **Backtest Credit system**: 25/50 credits (limits backtest runs)
- Run Backtest button

### 5. Strategy Templates
Pre-built strategies users can "Add to my strategy":
- **1% Strangle Nifty** — "A Nifty 50 intraday short strangle selling weekly ITM options to capture Theta. It employs a 1% stop-loss no fixed target..."
- **Golden Crossover Nifty Buying** — momentum-based Nifty option buying triggered by Moving Averages
- **Brahmastra Nifty Option Buying** — confluence of Moving Average MACD and Supertrend
- **1.5% SL Strangle BNF** — Bank Nifty short strangle
- **1% SL Strangle BNF**

### 6. Reports
- **Report** tab: Strategy Breakdown donut chart, Total P&L
- **Trade Engine Logs** tab
- Date range: From / To with calendar pickers
- Select Broker: All / specific broker
- **Live / Forward** toggle buttons
- Get Reports button

---

## What's Missing from QuantLab

### 🔴 Critical Gaps (Options Trading Focus)

| # | Missing Feature | Why It Matters | Effort |
|---|-----------------|----------------|--------|
| 1 | **Visual Strategy Builder** | User wants to build multi-leg option strategies (short straddle, strangle, spreads) without writing Python | High |
| 2 | **Option Chain Simulator** | User needs to see live strikes, select ATM/ITM/OTM, visualize payoff before backtesting | High |
| 3 | **Multi-leg Strategy Support** | Your strategy engine is single-leg. Need to support multiple legs with independent strike/SL/TP configs | Medium-High |
| 4 | **Strike Selection Engine** | ATM, ITM, OTM selection based on underlying price + configurable offset points | Medium |
| 5 | **Expiry Selection** | Weekly, Monthly, Next Weekly, etc. | Medium |
| 6 | **Strategy Templates** | Pre-built templates users can clone and modify | Low |
| 7 | **Day-of-Week Scheduling** | Only trade on MON, TUE, etc. | Low |
| 8 | **MIS/CNC/BTST Order Types** | Indian broker-specific order types | Low |

### 🟡 Medium Gaps

| # | Missing Feature | Why It Matters | Effort |
|---|-----------------|----------------|--------|
| 9 | **Backtest Credit System** | Could limit backtest runs to prevent server abuse | Low |
| 10 | **TradingView Signals Integration** | Allow external signals to trigger strategies | Medium |
| 11 | **Live/Forward Test Toggle** | Run strategies in paper mode before live | Medium |
| 12 | **Terminal Toggle / Trading Engine Toggle** | Direct control over broker terminal | Low |
| 13 | **Strategy Deployment Card** | Dashboard widget showing deployed strategy status | Low |
| 14 | **Dark Mode** | UI toggle | Low |
| 15 | **Wallet / Subscription** | Monetization features | Medium |

### 🟢 Already Present in QuantLab

| Feature | QuantLab Status |
|---------|-----------------|
| SmartAPI broker integration | ✅ |
| Backtest engine with replay | ✅ |
| Dataset diagnostics / quant analysis | ✅ (ResearchLab) |
| Position tracking | ✅ |
| Deployment orchestrator | ✅ |
| Multi-asset research | ✅ |
| Data download / management | ✅ |
| FUTURES/OPTIONS trade type support | ✅ (just added) |
| INTRADAY EOD squaring | ✅ (just added) |
| Broker-specific charges (STT, GST, etc.) | ✅ |

---

## Recommended Implementation Roadmap

### Phase 1: Option Chain + Simulator (Foundation)
1. **Option Chain Data Feed** — Fetch NIFTY/BANKNIFTY option chain from SmartAPI or NSE
2. **Option Chain UI** — React component showing strikes, prices, Delta, B/S buttons
3. **Payoff Visualization** — ECharts/Canvas chart showing P&L at expiration for selected legs
4. **Margin Estimator** — Calculate approximate SPAN+Exposure margin for selected legs

### Phase 2: Visual Strategy Builder
1. **Leg-Based Strategy Model** — DB schema: `StrategyLeg` table with position, type, strike_criteria, expiry, SL/TP
2. **Builder UI** — React component with `+ Add Leg` button, configure each leg visually
3. **Strategy Code Generator** — Generate Python code from visual config (or interpret config directly in backtester)
4. **Strategy Templates** — Pre-built templates: Short Straddle, Short Strangle, Iron Condor, etc.

### Phase 3: Enhanced Backtesting
1. **Strike Resolution** — At runtime, resolve "ATM", "ATM+100", "ITM-1" to actual strike prices from option chain
2. **Expiry Resolution** — Resolve "Weekly", "Next Weekly", "Monthly" to actual expiry dates
3. **Multi-leg Execution** — Backtester executes all legs simultaneously at entry time
4. **SL/TP per Leg** — Independent stop-loss and take-profit per leg

### Phase 4: Live Trading
1. **Paper Trading** — Live/Forward toggle for paper trading
2. **Strategy Deployment** — Deploy visual strategies to live broker
3. **Trade Engine Logs** — Log every decision from the deployed strategy

---

## Key Insight

Algorooms is **not a general-purpose quant platform** — it's a **specialized visual options strategy builder**. The user's original strategy generator was trying to be AI-driven, but Algorooms succeeds by being **visual, template-based, and focused on F&O**. The gap is not about adding more Python code features — it's about building a **visual UI layer** for options strategy construction.

The user's example strategy:
> SELL NIFTY 50 ATM 0 PE, Qty: 75  
> SELL NIFTY 50 ATM 0 CE, Qty: 75  
> Start: 09:15, End: 15:15, Segment: OPTION, Type: Indicator Based

This is a **2-leg short straddle** — exactly the kind of strategy Algorooms builds visually. In QuantLab, the user would need to write Python code for this. The missing piece is the visual builder that translates this config into executable backtest/live trades.
