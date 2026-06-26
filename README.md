# QuantLab

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Market-India%20%7C%20NSE-green" />
  <img src="https://img.shields.io/badge/Data-Real%20Candles%20Only-critical" />
</p>

**QuantLab** is a professional-grade quantitative trading platform built for Indian markets. It connects to **Angel One SmartAPI** for real historical data, runs sandboxed Python strategies, simulates real Indian market charges (STT, GST, SEBI, Stamp Duty), and visualizes everything through a premium Next.js dashboard with TradingView Lightweight Charts, ECharts, and the Monaco Editor.

---

## Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | System health, connection status, quick backtest launch, and live notifications |
| **Datasets** | Download real historical candles from SmartAPI with From/To date range filtering, async background jobs with progress tracking, universal data aggregator (chunking, merge, dedup, forward-fill), preview with interactive charts, file export (CSV/Excel), and symbol group / basket management |
| **Strategy Workspace** | Monaco Editor with Python templates, dual runtime support (`legacy_on_bar` / `prosperity_trader`), symbol/interval/capital configuration, auto max-position sizing from volatility, risk settings, and parameter JSON |
| **Backtests & Replay** | Event-driven engine with Indian charge simulation, equity/drawdown charts, per-symbol analytics, auto max-position sizing, data coverage validation, and frame-by-frame replay studio with speed controls |
| **Live Trading (Mock)** | Dedicated `/live` trading page with real-time market data, manual order placement, live PnL tracking, full charge breakdown, SSE event streaming, pause/resume deployments, reset capital, and deployment event logs |
| **Deployments** | Paper and live deployment management with status monitoring, pause/resume, capital reset, and full event history |
| **Research Lab** | Deep statistical analysis — returns, volatility, regime detection (HMM), seasonality, strategy-suitability scoring, mean-reversion diagnostics (Hurst, half-life), gap analysis, intraday behavior, volatility structure, tail risk, order-flow proxies, multi-timeframe analysis, factor exposure, walk-forward stability, feature-importance engine, and AI strategy generator |
| **Multi-Asset Research** | Correlation matrices, pair discovery, cointegration, spread analysis, lead-lag, sector breadth, rolling correlation, and cross-sectional factor ranking with From/To date range filtering |
| **Portfolio Risk** | Monte Carlo simulation, stress testing, risk-of-ruin, drawdown projections, confidence intervals, and daily PnL heatmaps |
| **Optimization Lab** | Grid/random search with Sharpe/Sortino/Calmar objectives, walk-forward validation, sensitivity analysis, and 3D surface plots |
| **Strategy Registry** | Market analysis, auto-ranking of registered strategies, walk-forward optimization with robustness scoring, overfit detection, and one-click deployment of the best configuration |
| **System Cleanup** | Log and dataset cleanup, database vacuum, and disk usage analytics |

> **Real Data Only.** The platform enforces real downloaded candles for all production backtests. No simulated or mock data is injected into the backtest engine.

---

## Dual Runtime Engine

QuantLab supports two strategy execution models side by side. You pick one per strategy:

| Runtime | Signature | Returns | Best For |
|---------|-----------|---------|----------|
| **legacy_on_bar** | `def on_bar(self, state)` | `list[dict]` | Quick backtests, single/multi-symbol, candle-based signals |
| **prosperity_trader** | `def run(self, state)` | `(orders, conversions, trader_data)` | Order-book-aware strategies, live trading, state persistence |

Both runtimes are sandboxed, charge-aware, and replay-compatible. The engine auto-detects your runtime from the strategy class and selects the correct adapter. See the sample files for a working EMA crossover in each style.

---

## Symbol Format

All symbols are automatically normalized to the canonical `NSE:SYMBOL-EQ` format across the entire stack:

- **Frontend** — type `SBIN`, it becomes `NSE:SBIN-EQ` before sending
- **Backend** — stored as `NSE:SBIN-EQ` in the database
- **Engine** — catalog lookups, backtests, and live data all use the canonical form

You never need to think about it. Just type the symbol name and everything resolves correctly.

---

## Screenshots

All screenshots were captured live from the running application on `localhost:3000` via Kimi WebBridge.

**Dashboard**
![Dashboard](/docs/screenshots/webbridge_homepage.png)

**Datasets — Real Historical Data Catalog**
![Datasets](/docs/screenshots/webbridge_datasets.png)

**Strategy Workspace — Monaco Editor & Configuration**
![Strategies](/docs/screenshots/webbridge_strategies.png)

**Backtest Simulation Engine**
![Backtests](/docs/screenshots/webbridge_backtests.png)

**Live Mock Trading (Paper Mode)**
![Live Trading](/docs/screenshots/webbridge_live.png)

**Live Trading — Order Book & Trades**
![Live Trades](/docs/screenshots/webbridge_live_trading.png)

**Research Lab — Statistical Diagnostics**
![Research Lab](/docs/screenshots/webbridge_tab_research.png)

**Multi-Asset Research — Correlation & Pair Analysis**
![Multi-Asset](/docs/screenshots/webbridge_tab_multiasset.png)

**Portfolio Risk — Monte Carlo Simulation**
![Portfolio Risk](/docs/screenshots/webbridge_tab_portfolio_risk.png)

**Optimizer — Grid Search Parameter Sweeps**
![Optimizer](/docs/screenshots/webbridge_tab_optimizer.png)

**System Cleanup — Disk & Database Maintenance**
![Cleanup](/docs/screenshots/webbridge_tab_cleanup.png)

**Dashboard Tab**
![Dashboard Tab](/docs/screenshots/webbridge_tab_dashboard.png)

**Backtests Tab**
![Backtests Tab](/docs/screenshots/webbridge_tab_backtests.png)

**Datasets Tab**
![Datasets Tab](/docs/screenshots/webbridge_tab_datasets.png)

**Deployments Tab**
![Deployments Tab](/docs/screenshots/webbridge_tab_deployments.png)

**Strategies Tab**
![Strategies Tab](/docs/screenshots/webbridge_tab_strategies.png)

---

## System Architecture

```mermaid
graph TD
    A[Next.js Frontend: Port 3000] -->|REST API / WebSockets| B[FastAPI Backend: Port 8000]
    B -->|Metadata & Run Catalog| C[(SQLite Database: quantlab.db)]
    B -->|SmartAPI Client| D[Angel One SmartAPI Gateway]
    B -->|Historical Data Download| E[Parquet Storage: /datasets]
    B -->|Task Trigger| F[Backtest Engine]
    F -->|Executes Code| G[Sandboxed Runtime]
    G -->|Runs| H[User Strategy: trader.py]
    F -->|Transaction Details| I[Execution Simulator]
    I -->|Calculates Fees| J[Indian Charges: STT/GST/Stamp Duty]
    F -->|Writes Logs| K[Replay Log Generator: /test_logs]
    B -->|Reads Logs| K
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 15, React, Tailwind CSS, TypeScript, Monaco Editor, TradingView Lightweight Charts, ECharts, Lucide Icons |
| **Backend** | FastAPI, Uvicorn, SQLAlchemy, SQLite, Pydantic, WebSockets, SSE, async background jobs |
| **Engine** | Python 3.10+, NumPy, Pandas, Parquet, sandboxed exec, event-driven loop, universal data aggregator |
| **Data** | Angel One SmartAPI, TOTP 2FA, CSV/Parquet/Excel storage, Redis-backed tick/candle cache |
| **AI/LLM** | Ollama integration for strategy assistance, research summarization, and AI strategy generation |

---

## Folder Structure

```
quantp/
├── backend/            # FastAPI application (main.py, database.py, smartapi.py, routers/)
│   ├── routers/        # API endpoints: auth, backtest, data, deployments, groups, live_trading, research, strategies
│   └── services/       # Data service, market data service, SmartAPI manager, Redis, Ollama, download jobs
├── engine/             # Core backtest, execution, analytics, and optimization modules
│   ├── runtime/        # Sandboxed strategy execution, adapters, datamodels
│   ├── analytics.py    # Risk metrics and performance attribution
│   ├── backtester.py   # Event-driven backtesting loop
│   ├── capital.py      # Capital requirements analysis
│   ├── data_analyzer.py# Deep independent dataset statistical analysis
│   ├── datamodels.py   # Core data models
│   ├── execution.py    # Order matching and charge calculation
│   ├── execution_engine.py # Order execution engine
│   ├── market.py       # Market data interface and regime detection
│   ├── market_interface.py # Unified market data interface
│   ├── monte_carlo.py  # Portfolio simulation
│   ├── optimization.py # Parameter search and walk-forward analysis
│   ├── order_manager.py# Order lifecycle management
│   ├── portfolio.py    # Portfolio tracking and sizing
│   ├── quant_analysis.py # Full quantitative analysis engine
│   ├── regime.py       # Market regime classification
│   ├── research.py     # Statistical research tools
│   ├── research_extras.py  # Seasonality, volume profile, S/R detection
│   ├── research_multiasset.py  # Multi-asset correlation and cointegration
│   ├── replay_logger.py        # Replay log generation
│   ├── sizing.py             # Position sizing logic
│   ├── strategy_codegen.py   # Auto-generated strategy code builder
│   ├── strategy_executor.py# Strategy execution wrapper
│   ├── strategy_generator.py # Strategy fitness scoring and config generator
│   ├── strategy_registry/    # Registry package: market analyzer, auto optimizer, performance metrics, reports
│   └── walk_forward.py       # Walk-forward optimization
├── frontend/           # Next.js 15 client app
│   ├── src/app/        # Pages, hooks, and layout
│   ├── src/components/ # React components: ResearchLab, MultiAssetResearch, PortfolioAnalytics, charts, StrategyRegistryTab
│   └── public/         # Static assets
├── datasets/           # Parquet/CSV/Excel historical candle storage
│   ├── csv/            # Symbol-named CSV files
│   ├── parquet/        # Efficient columnar storage
│   ├── excel/          # Excel exports
│   ├── catalog.json    # Dataset metadata index
│   ├── groups.yaml     # Symbol grouping definitions
│   └── symbol_tokens.json  # SmartAPI token mapping
├── docs/               # Documentation and screenshots
│   └── screenshots/    # UI screenshots captured via Kimi WebBridge
├── tests/              # Python unit tests and backtest verification scripts
├── sample_strategy_legacy.py      # EMA crossover example — legacy_on_bar runtime
├── sample_strategy_prosperity.py  # EMA crossover example — prosperity_trader runtime
├── .env                # Local secrets (ignored by Git)
├── .env.example        # Environment variable template
├── requirements.txt    # Python dependencies
├── quantlab.db         # SQLite database (auto-created)
└── README.md           # This file
```

---

## Prerequisites

- **Python 3.10+**
- **Node.js v18.0.0+**
- **NPM** (packaged with Node.js)
- **Git** (optional)

---

## Installation & Setup

### 1. Environment Configuration

Create a copy of `.env.example` and rename it to `.env`:

```bash
copy .env.example .env
```

Fill in your Angel One SmartAPI credentials:

```env
SMARTAPI_CLIENT_CODE="YOUR_CLIENT_CODE"
SMARTAPI_PASSWORD="YOUR_PASSWORD"
SMARTAPI_API_KEY="YOUR_API_KEY"
```

> **Note:** Without credentials, the platform still boots in a basic mode. You can still write and edit strategies, but live data download and mock trading require SmartAPI authentication.

---

### 2. Backend Setup

**Virtual environment (Windows):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Virtual environment (Linux / macOS):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Install dependencies:**
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Run the server:**
```bash
.venv\Scripts\python -m backend.main
```

The server starts on `http://0.0.0.0:8000` and auto-creates `quantlab.db`.

> **Important:** Always run with `python -m backend.main`, not `python backend/main.py`. The module path matters for imports.

---

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

---

### 4. Running Tests

```bash
pytest tests/
```

Or run the core test directly:
```bash
python tests/test_backtest.py
```

---

## Quickstart: Your First Backtest

### Step 1 — Download Data

1. Go to the **Datasets** tab in the sidebar
2. Enter a symbol like `SBIN` and interval `FIVE_MINUTE`
3. Use the **From** and **To** date pickers to select your exact range
4. Click **Download**
5. The backend runs the **universal data aggregator** — it chunks large requests into SmartAPI-safe ranges, merges results, deduplicates, validates coverage, and forward-fills any gaps
6. Track progress in real-time; large jobs run in the background and can be cancelled at any time

> Symbols are auto-normalized. Type `SBIN` and it resolves to `NSE:SBIN-EQ` everywhere.

### Step 2 — Create Symbol Groups (Optional)

1. Go to **Datasets** → **Groups**
2. Create a named basket like `BankNifty` with symbols `SBIN`, `ICICIBANK`, `HDFCBANK`
3. Use the group in multi-symbol backtests or multi-asset research

### Step 3 — Create a Strategy

1. Go to **Strategy Workspace**
2. Copy one of the included samples into the Monaco editor:
   - [`sample_strategy_legacy.py`](sample_strategy_legacy.py) — `legacy_on_bar` runtime
   - [`sample_strategy_prosperity.py`](sample_strategy_prosperity.py) — `prosperity_trader` runtime
3. Configure symbols, interval, capital, and max position size
4. Enable **Auto Max Position** to let the engine calculate size from recent volatility
5. Click **Save**

### Step 4 — Run Backtest

1. Go to the **Backtests** tab
2. Select your strategy, use the **From/To** date range, and configure slippage
3. Choose **INTRADAY** or **DELIVERY** trade type
4. The engine validates data coverage before running — if gaps exist, you get a clear warning
5. Click **Run**

The engine parses your strategy in a sandbox, steps through every candle, executes orders, applies real Indian market charges, and writes a replay log.

### Step 5 — Analyze

- **Replay Studio** — frame-by-frame playback with speed controls
- **Research Lab** — regime attribution, performance maps, mean-reversion diagnostics, and AI strategy generation
- **Portfolio Risk** — Monte Carlo simulations and stress tests
- **Optimization Lab** — parameter sweeps with walk-forward validation and sensitivity analysis
- **Strategy Registry** — market analysis, auto-ranking, walk-forward tuning, and one-click deployment of the best configuration

### Step 6 — Live Mock Trading

1. Go to the **Live Trading** page (`/live`) or the **Deployments** tab
2. Create a paper deployment with your strategy
3. Pause, resume, or reset capital at any time without restarting
4. View the full deployment event log for audit trails

---

## Advanced Capabilities

### Universal Data Aggregator

The download engine automatically handles large date ranges by:
- **Chunking** requests into SmartAPI-safe intervals
- **Merging** and **deduplicating** overlapping candles
- **Validating** coverage and warning about gaps before backtests
- **Forward-filling** missing candles so the engine never sees null data

> **Real Data Only.** The platform enforces real downloaded candles for all production backtests. No simulated or mock data is injected into the backtest engine.

### Async Download Jobs

Large downloads run as cancellable background jobs. The UI shows real-time progress, and you can cancel pending jobs without restarting the server.

### Symbol Groups & Baskets

Create named groups (e.g., `BankNifty`, `ITPack`) in `datasets/groups.yaml` via the Groups API. Use them for multi-symbol backtests, multi-asset correlation studies, and sector-breadth analysis.

### Auto Max Position Sizing

When enabled, the engine calculates a suggested max position from recent price volatility and your configured capital. You can override it manually or let the system size every backtest and deployment automatically.

### Strategy Registry & Auto Optimization

A full market-analysis pipeline that:
1. Analyzes current market conditions across all datasets
2. Ranks every registered strategy by suitability score
3. Runs walk-forward optimization with train/validation/test splits
4. Detects overfitting via robustness scoring and sensitivity analysis
5. Enables **one-click deployment** of the best configuration

### Live Trading Controls

Deployments support a full lifecycle:
- **Pause / Resume** — freeze a running paper deployment without losing state
- **Reset Capital** — adjust starting cash/equity mid-run
- **Event Log** — full audit trail of fills, errors, margin calls, and state transitions
- **Market Data Service** — centralized Redis-backed tick and candle cache shared across all deployments

### AI Strategy Generator

The Research Lab can auto-generate a complete strategy from quantitative analysis: entry/exit rules, position sizing, holding period, and expected win rate. Generated strategies can be saved to the StrategyDB and backtested in one click.

---

## Documentation

| File | Description |
|------|-------------|
| [`sample_strategy_legacy.py`](sample_strategy_legacy.py) | EMA crossover — `legacy_on_bar` runtime |
| [`sample_strategy_prosperity.py`](sample_strategy_prosperity.py) | EMA crossover — `prosperity_trader` runtime |
| [`requirements.txt`](requirements.txt) | Python dependencies |
| [`.env.example`](.env.example) | SmartAPI, Redis, and Ollama credentials template |
| [`datasets/groups.yaml`](datasets/groups.yaml) | Symbol basket definitions |
| [`datasets/catalog.json`](datasets/catalog.json) | Dataset metadata index |

---

## Troubleshooting

**PowerShell execution policy error**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Backend offline on frontend**
Ensure `python -m backend.main` is running on `http://127.0.0.1:8000`. Check `API_BASE` in `frontend/src/app/page.tsx` if you use a custom port.

**Dataset not found**
Download the symbol first in the **Datasets** tab. Bare symbols like `SBIN` are auto-resolved to `NSE:SBIN-EQ` — old records in the database are also canonicalized on read.

**Data coverage warning before backtest**
The engine validates that the requested date range has sufficient downloaded candles. If gaps exist, download the missing range in the **Datasets** tab, or the backtest will error out rather than use mock data.

**Async download job stuck**
Check the download status in the Datasets tab. Jobs can be cancelled and restarted. Large ranges may take a few minutes due to SmartAPI rate limits.

**Strategy sandbox error**
Check your Python syntax. Ensure your class matches the selected runtime:
- **Legacy:** `class Strategy` with `def on_bar(self, state):` returning `list[dict]`
- **Prosperity:** `class Trader` with `def run(self, state):` returning `(orders, conversions, trader_data)`

**Redis not available**
Redis is optional. Without it, the market data service falls back to in-memory caching. For production live-trading loads, start Redis and set `REDIS_URL` in `.env`.

---

## Contributing

Contributions are welcome. Good starting points:

- New strategy templates for the built-in gallery
- Additional chart types or visualizations
- New research and analytics modules
- Bug fixes and performance improvements
- Documentation improvements

---

## License

This project is open-source and available for personal and research use. Check the repository for the full license text.

---

<p align="center">
  <b>Built for Indian markets. Powered by real data. No shortcuts.</b>
</p>
