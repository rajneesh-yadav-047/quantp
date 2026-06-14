# QuantLab User Manual

> **Version:** 1.0  
> **Platform:** Professional-grade quantitative trading research, backtesting, replay, and visualization for Indian markets  
> **Markets:** NSE (India) via Angel One SmartAPI  
> **Data:** Real historical candles only — no simulated or mock data for production backtests

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dashboard](#2-dashboard)
3. [Datasets & Data Management](#3-datasets--data-management)
4. [Strategy Workspace](#4-strategy-workspace)
5. [Backtests & Replay](#5-backtests--replay)
6. [Live Trading (Mock)](#6-live-trading-mock)
7. [Deployments](#7-deployments)
8. [Research Lab](#8-research-lab)
9. [Multi-Asset Research](#9-multi-asset-research)
10. [Portfolio Risk Analytics](#10-portfolio-risk-analytics)
11. [Optimization Lab](#11-optimization-lab)
12. [System Cleanup](#12-system-cleanup)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Getting Started

### System Requirements
- **Python** 3.10+
- **Node.js** v18.0.0+
- **NPM** (packaged with Node.js)
- **Git** (optional)

### Quick Start
```bash
# 1. Configure credentials
copy .env.example.txt .env
# Edit .env with your Angel One SmartAPI credentials

# 2. Start the backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
.venv\Scripts\python -m backend.main

# 3. Start the frontend
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

> **Mock Mode:** If you do not have Angel One credentials, the platform boots into **Mock Mode** with realistic synthetic market data for testing.

---

## 2. Dashboard

The **Dashboard** is your mission control center. It provides:

- **System Health:** Live backend connection status, SmartAPI gateway status, and WebSocket state
- **Quick Actions:** One-click backtest launch, strategy selection, and date range configuration
- **Data Overview:** Count of downloaded datasets, saved strategies, and completed backtest runs
- **Notifications:** Real-time toast alerts for download completions, backtest finishes, and errors
- **TOTP Authentication:** Modal for secure two-factor login to Angel One SmartAPI

---

## 3. Datasets & Data Management

### Overview
All backtests require **real historical candle data** downloaded from Angel One SmartAPI. The platform stores data in **CSV**, **Parquet**, and **Excel** formats under `/datasets/`.

### Features
- **Symbol Search:** Auto-suggest with NSE symbol names (e.g., `SBIN`, `RELIANCE`, `NIFTY`)
- **Interval Selection:** `ONE_MINUTE`, `FIVE_MINUTE`, `FIFTEEN_MINUTE`, `THIRTY_MINUTE`, `ONE_HOUR`, `ONE_DAY`
- **Date Range:** Calendar-based start/end date pickers with range validation
- **Download Queue:** Async downloads with progress indicators and retry logic
- **Data Preview:** Interactive candlestick chart preview using **TradingView Lightweight Charts** before running backtests
- **Dataset Catalog:** JSON-indexed catalog of all available datasets with metadata
- **Group Management:** YAML-based symbol grouping for batch multi-symbol backtests

> **Real Data Only:** The system enforces real downloaded data for all production backtests. No simulated fallback data is injected into the backtest engine.

---

## 4. Strategy Workspace

### Overview
The **Strategy Workspace** is the primary development environment for writing, editing, and configuring trading strategies.

### Monaco Editor
- Full-featured **Monaco Editor** (VS Code engine) with Python syntax highlighting
- Pre-loaded templates: **EMA Crossover**, **RSI Mean Reversion**, **Multi-Symbol Strategy**
- Error diagnostics and code formatting
- File upload: drag-and-drop `.py` strategy files directly into the editor

### Strategy Configuration
| Parameter | Description |
|-----------|-------------|
| **Symbols** | Comma-separated NSE symbols (e.g., `SBIN,RELIANCE`) |
| **Interval** | Candle granularity: `ONE_MINUTE` to `ONE_DAY` |
| **Capital** | Starting capital in INR (e.g., `100,000`) |
| **Max Position** | Maximum shares/contracts per position |
| **Runtime Type** | Sandboxed Python execution engine |
| **Entry Point** | Function name that the engine calls (`on_bar`) |
| **Parameters** | JSON key-value pairs for strategy tuning |
| **Risk Settings** | Per-trade risk limits, stop-loss, and drawdown guards |

### Strategy Persistence
All strategies are saved to the **SQLite database** (`quantlab.db`) with versioning and metadata.

---

## 5. Backtests & Replay

### Running a Backtest
1. Select a saved strategy from the workspace
2. Set the **date range** and **slippage** (realistic execution delay)
3. Choose **trade type**: `INTRADAY` or `DELIVERY`
4. Configure **auto-max position** or set a manual cap
5. Click **Run Backtest**

### Backtest Engine Features
- **Event-Driven Loop:** Candle-by-candle execution simulating real market tick flow
- **Order Matching:** Simulated limit and market order fills with queue priority
- **Indian Charges Engine:** Exact calculation of:
  - Brokerage
  - STT (Securities Transaction Tax)
  - GST (18%)
  - SEBI Charges
  - Stamp Duty
  - Exchange Transaction Charges
- **Sandbox Runtime:** Isolated Python execution environment for user strategies
- **Multi-Symbol Support:** Backtest multiple symbols simultaneously with per-symbol attribution

### Results & Analytics
- **Equity Curve:** Interactive PnL chart over time
- **Drawdown Chart:** Peak-to-trough underwater visualization
- **Trade History:** Complete ledger with timestamps, prices, quantities, and fees
- **Per-Symbol Performance:** Sharpe, Sortino, win rate, and expectancy per ticker
- **Position Timeline:** Visual map of when positions were opened and closed
- **Replay Studio:** Step-by-step playback with speed control (0.5x to 10x), pause, and frame-by-frame scrubbing

---

## 6. Live Trading (Mock)

### Overview
**Live Trading** provides a real-time mock trading environment connected to live market data. No real money is used.

### Features
- **Real-Time Data:** Live candle stream via SmartAPI Market Data Service (MDS) or WebSocket
- **Manual Trading:** Place BUY/SELL market and limit orders with quantity input
- **Portfolio Tracker:** Real-time cash, equity, margin used, and margin free
- **PnL Monitoring:** Unrealized and realized PnL with total fee aggregation
- **Trade Ledger:** Every simulated trade with full charge breakdown (STT, GST, SEBI, Stamp Duty, Brokerage)
- **Event Stream:** Server-Sent Events (SSE) for live deployment status, errors, and trade confirmations
- **Capital Reset:** Reset portfolio capital to any amount for testing
- **Deployment Lifecycle:** Start, pause, resume, and stop deployments

### Charge Transparency
Every trade shows the exact charge breakdown, so you know the true cost of every simulated transaction before going live with a real broker.

---

## 7. Deployments

### Overview
Manage **paper trading** and **live deployment** configurations per strategy.

### Features
- **Deployment List:** View all active and historical deployments
- **Per-Strategy Binding:** Link a deployment to a specific strategy and dataset
- **Status Monitoring:** Real-time `running`, `paused`, `stopped`, or `error` states
- **Event History:** Chronological log of all deployment events and errors
- **Auto-Restart:** Optional auto-recovery on connection drops

---

## 8. Research Lab

### Overview
The **Research Lab** is a deep statistical analysis suite for any downloaded dataset. It answers the question: *"What kind of market is this, and what strategy fits it?"*

### Analysis Modules
| Module | Description |
|--------|-------------|
| **Returns Analysis** | Distribution, skewness, kurtosis, daily/monthly/annualized returns |
| **Volatility Profile** | Rolling volatility, GARCH estimation, volatility clustering |
| **Regime Detection** | Trending vs. ranging classification using HMM and moving averages |
| **Seasonality** | Day-of-week, month-of-year, and holiday effects |
| **Strategy Suitability** | Score-based matching of dataset characteristics to strategy archetypes |
| **Drawdown Analysis** | Maximum drawdown, recovery time, and underwater curve |
| **Tail Risk** | VaR, CVaR, and extreme loss event frequency |

### Visualization
- **ECharts** powered interactive charts
- Heatmaps, histograms, regime overlays, and rolling metric bands
- Exportable data tables for Excel/CSV

---

## 9. Multi-Asset Research

### Overview
Analyze relationships between multiple symbols to build pairs, baskets, and spread strategies.

### Features
- **Correlation Matrix:** Pearson and Spearman correlation heatmaps
- **Pair Discovery:** Automated cointegration testing and ADF test results
- **Spread Analysis:** Mean-reverting spread visualization with Z-score bands
- **Lead-Lag Analysis:** Granger causality and cross-correlation lag detection
- **Sector Breadth:** Advance/decline ratios and sector rotation indicators
- **Factor Ranking:** Multi-factor scoring (momentum, value, quality) for universe ranking

---

## 10. Portfolio Risk Analytics

### Overview
Simulate portfolio-level risk before committing capital.

### Features
- **Monte Carlo Simulation:** 10,000+ path simulations of portfolio returns
- **Stress Testing:** Scenario-based shocks (e.g., -20% single-day drop, volatility spike)
- **Risk of Ruin:** Probability of capital depletion given win rate and payoff ratio
- **Drawdown Projections:** Expected maximum drawdown with confidence intervals
- **Confidence Intervals:** 95% and 99% VaR/CVaR at portfolio level
- **Kelly Criterion:** Optimal position sizing based on edge and odds

---

## 11. Optimization Lab

### Overview
Search for mathematically optimal strategy parameters using brute-force and randomized search algorithms.

### Features
- **Grid Search:** Exhaustive parameter sweep over a defined range
- **Random Search:** Stochastic exploration for high-dimensional spaces
- **Objective Functions:** Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max Drawdown, Win Rate
- **Constraint Engine:** Minimum trades, maximum drawdown, and capital limits
- **Parallel Execution:** Multi-core parameter evaluation
- **3D Surface Plots:** Visualize parameter landscapes with ECharts
- **Walk-Forward Analysis:** Out-of-sample validation to prevent overfitting

---

## 12. System Cleanup

### Overview
Manage disk space and database hygiene over time.

### Features
- **Log Cleanup:** Delete old backtest replay logs (`/logs/*.jsonl`)
- **Dataset Cleanup:** Remove unused CSV/Parquet/Excel files
- **Database Vacuum:** Compact and optimize SQLite database size
- **Bulk Operations:** Selective or global deletion with confirmation dialogs
- **Space Usage:** Visual breakdown of disk usage by category

---

## 13. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Backend Offline** | Ensure `python -m backend.main` is running on port `8000`. Check CORS settings if using custom ports. |
| **SmartAPI Disconnected** | Verify `.env` credentials. Use TOTP modal to re-authenticate. |
| **Dataset Not Found** | Download the dataset first in the **Datasets** tab. Ensure the symbol and interval match. |
| **Parquet Error** | Re-download the dataset; the Parquet file may be corrupted. |
| **Strategy Sandbox Error** | Check Python syntax in the Monaco Editor. Ensure the `on_bar` function signature matches the template. |
| **PowerShell Execution Policy** | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` as Administrator. |
| **Frontend Port Conflict** | If `3000` is taken, change the port in `frontend/package.json` or run `npm run dev -- --port 3001`. |

### Logs & Debug
- **Backend Logs:** Console output from `uvicorn` and custom `INFO`/`ERROR` loggers
- **Replay Logs:** JSONL files in `/logs/` for every backtest run
- **Browser Console:** Frontend React errors and API fetch failures
- **Database Inspection:** `quantlab.db` can be opened with any SQLite viewer (e.g., DB Browser for SQLite)

---

## Architecture Quick Reference

```
┌─────────────────┐     REST API / WS      ┌─────────────────┐
│  Next.js Client │  <──────────────────>  │  FastAPI Server │  Port 8000
│   (Port 3000)   │                        │   (Port 8000)   │
└─────────────────┘                        └─────────────────┘
                                                    │
           ┌────────────────────────────────────────┼────────┐
           │                                        │        │
           ▼                                        ▼        ▼
    ┌─────────────┐                        ┌─────────────┐  ┌─────────────┐
    │  SQLite DB  │                        │ SmartAPI GW │  │   Parquet   │
    │ quantlab.db │                        │ Angel One   │  │  /datasets  │
    └─────────────┘                        └─────────────┘  └─────────────┘
```

---

## Support & Contributions

QuantLab is an open-source quantitative research platform built for the Indian market. For feature requests, bug reports, or contributions, please open an issue on GitHub.

**Happy backtesting!** 🚀
