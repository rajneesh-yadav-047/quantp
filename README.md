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
| **Datasets** | Download real historical candles from SmartAPI, preview with interactive charts, manage CSV/Parquet/Excel storage |
| **Strategy Workspace** | Monaco Editor with Python templates, dual runtime support, symbol/interval/capital configuration, risk settings, and parameter JSON |
| **Backtests & Replay** | Event-driven engine with Indian charge simulation, equity/drawdown charts, per-symbol analytics, and frame-by-frame replay studio |
| **Live Trading (Mock)** | Real-time market data, manual order placement, live PnL tracking, full charge breakdown, and SSE event streaming |
| **Deployments** | Paper and live deployment management with status monitoring and event history |
| **Research Lab** | Deep statistical analysis — returns, volatility, regime detection, seasonality, and strategy suitability scoring |
| **Multi-Asset Research** | Correlation matrices, pair discovery, cointegration, spread analysis, lead-lag, and sector breadth |
| **Portfolio Risk** | Monte Carlo simulation, stress testing, risk-of-ruin, drawdown projections, and confidence intervals |
| **Optimization Lab** | Grid/random search with Sharpe/Sortino/Calmar objectives, walk-forward validation, and 3D surface plots |
| **System Cleanup** | Log and dataset cleanup, database vacuum, and disk usage analytics |

> **Real Data Only.** The platform enforces real downloaded candles for all production backtests. No simulated or mock data is injected into the backtest engine.

---

## Dual Runtime Engine

QuantLab supports two strategy execution models side by side. You pick one per strategy:

| Runtime | Signature | Returns | Best For |
|---------|-----------|---------|----------|
| **legacy_on_bar** | `def on_bar(self, state)` | `list[dict]` | Quick backtests, single/multi-symbol, candle-based signals |
| **prosperity_trader** | `def run(self, state)` | `(orders, conversions, trader_data)` | Order-book-aware strategies, live trading, state persistence |

Both runtimes are sandboxed, charge-aware, and replay-compatible. See the sample files for a working EMA crossover in each style.

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
| **Backend** | FastAPI, Uvicorn, SQLAlchemy, SQLite, Pydantic, WebSockets, SSE |
| **Engine** | Python 3.10+, NumPy, Pandas, Parquet, sandboxed exec, event-driven loop |
| **Data** | Angel One SmartAPI, TOTP 2FA, CSV/Parquet/Excel storage, Redis (optional) |
| **AI/LLM** | Ollama integration for strategy assistance and research summarization |

---

## Folder Structure

```
quantp/
├── backend/            # FastAPI application (main.py, database.py, smartapi.py, routers/)
│   ├── routers/        # API endpoints: auth, backtest, data, deployments, groups, live_trading, research, strategies
│   └── services/       # Data service, market data service, SmartAPI manager, Redis, Ollama
├── engine/             # Core backtest, execution, analytics, and optimization modules
│   ├── runtime/        # Sandboxed strategy execution, adapters, datamodels
│   ├── analytics.py    # Risk metrics and performance attribution
│   ├── backtester.py   # Event-driven backtesting loop
│   ├── execution.py    # Order matching and charge calculation
│   ├── market.py       # Market data interface and regime detection
│   ├── monte_carlo.py  # Portfolio simulation
│   ├── optimization.py # Parameter search and walk-forward analysis
│   ├── portfolio.py    # Portfolio tracking and sizing
│   ├── regime.py       # Market regime classification
│   ├── research.py     # Statistical research tools
│   ├── research_multiasset.py  # Multi-asset correlation and cointegration
│   ├── replay_logger.py        # Replay log generation
│   └── walk_forward.py       # Walk-forward optimization
├── frontend/           # Next.js 15 client app
│   ├── src/app/        # Pages, hooks, and layout
│   ├── src/components/ # React components: ResearchLab, MultiAssetResearch, PortfolioAnalytics, charts
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
├── .env.example.txt    # Environment variable template
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

Create a copy of `.env.example.txt` and rename it to `.env`:

```bash
copy .env.example.txt .env
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
3. Pick a date range and click **Download**
4. The backend fetches real candles from SmartAPI, indexes them, and stores them locally

> Symbols are auto-normalized. Type `SBIN` and it resolves to `NSE:SBIN-EQ` everywhere.

### Step 2 — Create a Strategy

1. Go to **Strategy Workspace**
2. Copy one of the included samples into the Monaco editor:
   - [`sample_strategy_legacy.py`](sample_strategy_legacy.py) — `legacy_on_bar` runtime
   - [`sample_strategy_prosperity.py`](sample_strategy_prosperity.py) — `prosperity_trader` runtime
3. Configure symbols, interval, capital, and max position size
4. Click **Save**

### Step 3 — Run Backtest

1. Go to the **Backtests** tab
2. Select your strategy, set a date range, and configure slippage
3. Choose **INTRADAY** or **DELIVERY** trade type
4. Click **Run**

The engine parses your strategy in a sandbox, steps through every candle, executes orders, applies real Indian market charges, and writes a replay log.

### Step 4 — Analyze

- **Replay Studio** — frame-by-frame playback with speed controls
- **Research Lab** — regime attribution and performance maps
- **Portfolio Risk** — Monte Carlo simulations and stress tests
- **Optimization Lab** — parameter sweeps with walk-forward validation

---

## Documentation

| File | Description |
|------|-------------|
| [`sample_strategy_legacy.py`](sample_strategy_legacy.py) | EMA crossover — `legacy_on_bar` runtime |
| [`sample_strategy_prosperity.py`](sample_strategy_prosperity.py) | EMA crossover — `prosperity_trader` runtime |
| [`requirements.txt`](requirements.txt) | Python dependencies |
| [`.env.example.txt`](.env.example.txt) | SmartAPI credentials template |

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

**Strategy sandbox error**
Check your Python syntax. Ensure your class matches the selected runtime:
- **Legacy:** `class Strategy` with `def on_bar(self, state):` returning `list[dict]`
- **Prosperity:** `class Trader` with `def run(self, state):` returning `(orders, conversions, trader_data)`

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
