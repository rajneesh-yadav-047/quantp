"""
Research router: regime attribution, capital analysis, optimization,
independent dataset deep analysis, AND multi-asset research analytics.
"""

import time
import json
import math
from typing import Any, cast, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, BacktestResultDB, StrategyDB
from backend.smartapi import SmartAPIClient
from backend.services.data_service import slice_dataframe_by_date
from engine.research import attribute_performance_by_regime
from engine.capital import analyze_capital_requirements
from engine.optimization import run_parameter_sweep, run_random_search, sensitivity_analysis, build_heatmap, detect_overfitting
from engine.data_analyzer import analyze_dataset
from engine.market import Market, market_from_dict
import engine.research_multiasset as ma

router = APIRouter(prefix="/api/research", tags=["research"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DatasetAnalysisRequest(BaseModel):
    symbol: str
    interval: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MultiAssetCorrelationRequest(BaseModel):
    """Request correlation / sector analytics across multiple symbols."""
    symbols: List[str]
    interval: str
    window: Optional[int] = 60
    log_returns: bool = True


class PairDiscoveryRequest(BaseModel):
    symbols: List[str]
    interval: str
    top_n: int = 10
    min_corr: float = 0.6


class CointegrationRequest(BaseModel):
    sym1: str
    sym2: str
    interval: str


class SpreadAnalysisRequest(BaseModel):
    sym1: str
    sym2: str
    interval: str
    hedge_ratio: float = 1.0
    zscore_window: int = 20


class LeadLagRequest(BaseModel):
    symbols: List[str]
    interval: str
    max_lag: int = 5


class CrossSectionalRankRequest(BaseModel):
    symbols: List[str]
    interval: str
    factor: str = "momentum"   # 'momentum' | 'volatility' | 'sharpe'
    lookback: int = 20


class OptimizationRequest(BaseModel):
    strategy_id: str
    symbol: str
    interval: str
    start_date: str
    end_date: str
    param_grid_json: str
    initial_capital: float = 100000.0
    trade_type: str = "INTRADAY"
    search_type: str = "grid"         # 'grid' | 'random'
    n_trials: int = 30                # for random search


class MonteCarloRequest(BaseModel):
    run_id: str
    n_simulations: int = 1000


class WalkForwardRequest(BaseModel):
    strategy_id: str
    symbols: List[str]
    interval: str
    start_date: str
    end_date: str
    param_grid_json: str
    initial_capital: float = 100000.0
    trade_type: str = "INTRADAY"
    train_size: int = 200
    val_size: int = 50
    test_size: int = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_multi_symbol_data(
    client: SmartAPIClient,
    symbols: List[str],
    interval: str,
    auto_download: bool = False,
) -> Dict[str, Any]:
    """Load dataframes for a list of symbols using SmartAPIClient.

    Normalizes bare symbols (e.g. SBIN -> NSE:SBIN-EQ) and attempts auto-download
    if a connected client is available and auto_download=True.
    """
    from backend.services.data_service import normalize_symbol, load_or_download_symbol_data
    import pandas as pd
    data = {}
    # Default date range for research auto-download: last 60 days
    today = pd.Timestamp.now().normalize()
    start_date = (today - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    for sym in symbols:
        bare = sym.upper().strip()
        if not bare:
            continue
        # Normalize to canonical form so catalog lookup works
        normalized = normalize_symbol(bare, interval, client)
        # Try loading with the normalized key first
        df = client.load_dataset_csv(normalized, interval.upper())
        if df is None or df.empty:
            # Fallback: try the bare key (backward compat)
            df = client.load_dataset_csv(bare, interval.upper())
        if (df is None or df.empty) and auto_download and client and client.jwt_token:
            try:
                df_fetched, is_mock = client.fetch_historical_candles(
                    symbol=normalized,
                    from_date=f"{start_date} 09:15",
                    to_date=f"{end_date} 15:30",
                    interval=interval,
                )
                if not is_mock and df_fetched is not None and not df_fetched.empty:
                    client.save_dataset_csv(normalized, interval, df_fetched, is_mock=False)
                    df = df_fetched
                    time.sleep(0.5)  # rate-limit padding
            except Exception as e:
                print(f"WARN: Auto-download failed for {normalized}: {e}")
        if df is not None and not df.empty:
            data[normalized] = df
    return data


def _prices_wide(data: Dict[str, Any]) -> Any:
    """Build a wide close-price DataFrame from symbol -> df mapping."""
    import pandas as pd
    frames = {}
    for sym, df in data.items():
        if "close" in df.columns:
            if "time" in df.columns:
                s = df.set_index("time")["close"].astype(float)
            else:
                s = df["close"].astype(float)
            frames[sym] = s
    if not frames:
        return None
    wide = pd.DataFrame(frames)
    wide.index = pd.to_datetime(wide.index, errors="coerce")
    return wide.sort_index().dropna(how="all")


# ---------------------------------------------------------------------------
# Existing single-asset endpoints (unchanged)
# ---------------------------------------------------------------------------

@router.post("/analyze")
def analyze_dataset_endpoint(req: DatasetAnalysisRequest):
    """Deep statistical analysis of a dataset — completely independent of backtest results."""
    client = SmartAPIClient()
    lookup_key = f"{req.symbol.upper()}_{req.interval.upper()}"
    catalog = client.load_catalog()
    print(f"DEBUG research/analyze: looking for key={lookup_key}, catalog_keys={list(catalog.keys())}")

    df = client.load_dataset_csv(req.symbol.upper(), req.interval.upper())
    if df is None:
        raise HTTPException(status_code=404, detail=f"Dataset not found in catalog. (looked for: {lookup_key}, available: {list(catalog.keys())})")
    if df.empty:
        raise HTTPException(status_code=404, detail="Dataset empty after loading.")

    if req.start_date and req.end_date:
        try:
            df = slice_dataframe_by_date(df, req.start_date, req.end_date)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Date slicing error: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset empty after date filtering.")

    result = analyze_dataset(df=df, symbol=req.symbol.upper(), interval=req.interval.upper())
    return result


@router.get("/regimes/{run_id}")
def get_regime_attribution(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    client = SmartAPIClient()
    df = client.load_dataset_csv(cast(str, r.symbol), cast(str, r.interval))
    if df is None:
        raise HTTPException(status_code=404, detail="Original dataset missing from catalog.")

    from backend.routers.backtest import get_backtest_logs
    events = get_backtest_logs(run_id, db)
    trades = []
    for ev in events:
        trades.extend(ev.get("orders_filled", []))

    attribution = attribute_performance_by_regime({cast(str, r.symbol): df}, trades)
    return attribution


@router.get("/capital/analysis/{run_id}")
def get_capital_analysis(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    s = db.query(StrategyDB).filter(StrategyDB.id == r.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy script missing in DB.")

    client = SmartAPIClient()
    df = client.load_dataset_csv(cast(str, r.symbol), cast(str, r.interval))
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    df = slice_dataframe_by_date(df, cast(str, r.start_time), cast(str, r.end_time))
    df_dict = {cast(str, r.symbol): df}
    analysis = analyze_capital_requirements(
        df_dict=df_dict,
        strategy_code=cast(str, s.code),
        default_trade_type=cast(str, r.interval),
    )
    return analysis


@router.post("/optimize")
def run_optimization(req: OptimizationRequest, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    client = SmartAPIClient()
    df = client.load_dataset_csv(req.symbol, req.interval)
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    df = slice_dataframe_by_date(df, req.start_date, req.end_date)
    df_dict = {req.symbol.upper(): df}

    try:
        param_grid = json.loads(req.param_grid_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid param_grid_json string.")

    if req.search_type == "random":
        sweep_results = run_random_search(
            df_dict=df_dict,
            strategy_code=cast(str, s.code),
            param_grid=param_grid,
            n_trials=req.n_trials,
            initial_capital=req.initial_capital,
            default_trade_type=req.trade_type,
        )
    else:
        sweep_results = run_parameter_sweep(
            df_dict=df_dict,
            strategy_code=cast(str, s.code),
            param_grid=param_grid,
            initial_capital=req.initial_capital,
            default_trade_type=req.trade_type,
        )

    # Add sensitivity analysis
    sens = sensitivity_analysis(sweep_results.get("results", []))
    sweep_results["sensitivity"] = sens
    return sweep_results


# ---------------------------------------------------------------------------
# New Multi-Asset endpoints
# ---------------------------------------------------------------------------

@router.post("/multiasset/correlation")
def multiasset_correlation(req: MultiAssetCorrelationRequest):
    """Compute correlation matrix and sector heatmap for a set of symbols."""
    client = SmartAPIClient()
    data = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    if not data:
        missing = [s for s in req.symbols if s.upper().strip() not in data]
        raise HTTPException(status_code=404, detail=f"No data found for requested symbols. Loaded: {list(data.keys())}. Missing: {missing}")

    prices = _prices_wide(data)
    if prices is None or prices.empty:
        raise HTTPException(status_code=400, detail="Could not build price matrix.")

    # Last `window` rows
    if req.window and len(prices) > req.window:
        prices_window = prices.iloc[-req.window:]
    else:
        prices_window = prices

    corr_matrix = ma.correlation_matrix(prices_window, log_returns=req.log_returns)

    return {
        "symbols": list(prices.columns),
        "correlation_matrix": corr_matrix.round(4).to_dict(),
        "n_bars_used": len(prices_window),
    }


@router.post("/multiasset/rolling-correlation")
def rolling_correlation(req: MultiAssetCorrelationRequest):
    """Return rolling correlation time series for all pairs."""
    if len(req.symbols) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 symbols.")
    client = SmartAPIClient()
    data = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    prices = _prices_wide(data)
    if prices is None or prices.empty:
        raise HTTPException(status_code=400, detail="Could not build price matrix.")

    syms = list(prices.columns)
    result = {}
    window = req.window or 20
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            s1, s2 = syms[i], syms[j]
            rc = ma.rolling_correlation(prices, s1, s2, window=window, log_returns=req.log_returns)
            result[f"{s1}/{s2}"] = rc.dropna().round(4).tolist()

    return {"window": window, "pairs": result}


@router.post("/multiasset/pair-discovery")
def pair_discovery(req: PairDiscoveryRequest):
    """Discover statistically interesting pairs from a symbol universe."""
    client = SmartAPIClient()
    data = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    prices = _prices_wide(data)
    if prices is None or prices.empty:
        raise HTTPException(status_code=400, detail="Could not build price matrix.")

    pairs = ma.discover_pairs(prices, top_n=req.top_n, min_corr=req.min_corr)
    return {"pairs": pairs, "symbols_loaded": list(prices.columns)}


@router.post("/multiasset/cointegration")
def cointegration(req: CointegrationRequest):
    """Test cointegration between two symbols."""
    from backend.services.data_service import normalize_symbol
    client = SmartAPIClient()
    n1 = normalize_symbol(req.sym1.upper(), req.interval, client)
    n2 = normalize_symbol(req.sym2.upper(), req.interval, client)
    df1 = client.load_dataset_csv(n1, req.interval.upper())
    if df1 is None or df1.empty:
        df1 = client.load_dataset_csv(req.sym1.upper(), req.interval.upper())
    df2 = client.load_dataset_csv(n2, req.interval.upper())
    if df2 is None or df2.empty:
        df2 = client.load_dataset_csv(req.sym2.upper(), req.interval.upper())
    if df1 is None or df2 is None:
        raise HTTPException(status_code=404, detail=f"One or both datasets not found. Looked for {n1} and {n2}.")

    s1 = df1.set_index("time")["close"].astype(float) if "time" in df1.columns else df1["close"].astype(float)
    s2 = df2.set_index("time")["close"].astype(float) if "time" in df2.columns else df2["close"].astype(float)
    s1, s2 = s1.align(s2, join="inner")

    result = ma.cointegration_test(s1, s2)
    result["sym1"] = req.sym1.upper()
    result["sym2"] = req.sym2.upper()
    return result


@router.post("/multiasset/spread-analysis")
def spread_analysis(req: SpreadAnalysisRequest):
    """Compute spread, half-life, and z-score for a symbol pair."""
    import pandas as pd
    from backend.services.data_service import normalize_symbol
    client = SmartAPIClient()
    n1 = normalize_symbol(req.sym1.upper(), req.interval, client)
    n2 = normalize_symbol(req.sym2.upper(), req.interval, client)
    df1 = client.load_dataset_csv(n1, req.interval.upper())
    if df1 is None or df1.empty:
        df1 = client.load_dataset_csv(req.sym1.upper(), req.interval.upper())
    df2 = client.load_dataset_csv(n2, req.interval.upper())
    if df2 is None or df2.empty:
        df2 = client.load_dataset_csv(req.sym2.upper(), req.interval.upper())
    if df1 is None or df2 is None:
        raise HTTPException(status_code=404, detail=f"One or both datasets not found. Looked for {n1} and {n2}.")

    s1 = df1.set_index("time")["close"].astype(float) if "time" in df1.columns else df1["close"].astype(float)
    s2 = df2.set_index("time")["close"].astype(float) if "time" in df2.columns else df2["close"].astype(float)
    s1, s2 = s1.align(s2, join="inner")

    spread = ma.compute_spread(s1, s2, hedge_ratio=req.hedge_ratio)
    hl = ma.half_life(spread)
    zs = ma.z_score_series(spread, window=req.zscore_window)

    return {
        "sym1": req.sym1.upper(),
        "sym2": req.sym2.upper(),
        "hedge_ratio": req.hedge_ratio,
        "half_life_bars": round(hl, 2) if math.isfinite(hl) else None,
        "current_zscore": round(float(zs.dropna().iloc[-1]), 4) if not zs.dropna().empty else None,
        "spread_series": spread.round(4).tolist()[-200:],
        "zscore_series": zs.dropna().round(4).tolist()[-200:],
    }


@router.post("/multiasset/lead-lag")
def lead_lag(req: LeadLagRequest):
    """Detect lead-lag relationships between symbols."""
    client = SmartAPIClient()
    data = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    prices = _prices_wide(data)
    if prices is None or prices.empty:
        raise HTTPException(status_code=400, detail="Could not build price matrix.")

    result = ma.lead_lag_detection(prices, max_lag=req.max_lag)
    return {"relationships": result}


@router.post("/multiasset/breadth")
def sector_breadth_endpoint(req: MultiAssetCorrelationRequest):
    """Compute sector breadth indicators."""
    client = SmartAPIClient()
    data = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    prices = _prices_wide(data)
    if prices is None or prices.empty:
        raise HTTPException(status_code=400, detail="Could not build price matrix.")

    window = req.window or 20
    result = ma.sector_breadth(prices, window=window)
    return result


@router.post("/multiasset/ranking")
def cross_sectional_ranking_endpoint(req: CrossSectionalRankRequest):
    """Cross-sectional factor ranking of symbols."""
    client = SmartAPIClient()
    data = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    prices = _prices_wide(data)
    if prices is None or prices.empty:
        raise HTTPException(status_code=400, detail="Could not build price matrix.")

    ranking_df = ma.cross_sectional_ranking(prices, factor=req.factor, lookback=req.lookback)
    return {"factor": req.factor, "lookback": req.lookback, "rankings": ranking_df.to_dict(orient="records")}


@router.post("/multiasset/monte-carlo")
def monte_carlo_endpoint(req: MonteCarloRequest, db: Session = Depends(get_db)):
    """Monte Carlo simulation on backtest trade P&L."""
    from engine.analytics import match_trades_fifo
    from engine.monte_carlo import simulate_trade_sequences, stress_test

    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == req.run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    from backend.routers.backtest import get_backtest_logs
    events = get_backtest_logs(req.run_id, db)
    trades = []
    for ev in events:
        trades.extend(ev.get("orders_filled", []))

    matched = match_trades_fifo(trades)
    pnls = [m["pnl"] for m in matched]

    if not pnls:
        raise HTTPException(status_code=400, detail="No matched trades found for simulation.")

    mc_result = simulate_trade_sequences(
        trade_pnls=pnls,
        n_simulations=req.n_simulations,
        initial_capital=float(r.initial_capital),
    )
    stress = stress_test(pnls, initial_capital=float(r.initial_capital))
    return {"monte_carlo": mc_result, "stress_test": stress}


@router.post("/multiasset/walk-forward")
def walk_forward_endpoint(req: WalkForwardRequest, db: Session = Depends(get_db)):
    """Walk-forward validation of a strategy."""
    from engine.walk_forward import WalkForwardTester
    from engine.backtester import BacktestEngine
    from engine.analytics import calculate_metrics

    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    client = SmartAPIClient()
    df_dict = _load_multi_symbol_data(client, req.symbols, req.interval, auto_download=True)
    if not df_dict:
        raise HTTPException(status_code=404, detail="No data found for any symbol.")

    # Slice to date range
    for sym in list(df_dict.keys()):
        df_dict[sym] = slice_dataframe_by_date(df_dict[sym], req.start_date, req.end_date)

    try:
        param_grid = json.loads(req.param_grid_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid param_grid_json.")

    # Use first param combo as default
    import itertools
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = [dict(zip(keys, v)) for v in itertools.product(*values)]
    params = combos[0] if combos else {}

    def strategy_fn(data, p):
        engine = BacktestEngine(
            df_dict=data,
            strategy_code=cast(str, s.code),
            initial_capital=req.initial_capital,
            default_trade_type=req.trade_type,
            parameters=p,
        )
        return engine.run()

    def metrics_fn(res):
        m = calculate_metrics(res.get("equity_curve", []), res.get("trades", []), req.initial_capital)
        return {
            "total_return": m.get("return_pct", 0.0),
            "sharpe": m.get("sharpe_ratio", 0.0),
            "max_dd": m.get("max_drawdown", 0.0),
        }

    tester = WalkForwardTester(
        df_dict=df_dict,
        strategy_fn=strategy_fn,
        train_size=req.train_size,
        val_size=req.val_size,
        test_size=req.test_size,
    )
    result = tester.run(params=params, metrics_fn=metrics_fn)
    return result


# ---------------------------------------------------------------------------
# Portfolio attribution endpoint
# ---------------------------------------------------------------------------

class AttributionRequest(BaseModel):
    run_id: str


@router.post("/multiasset/attribution")
def portfolio_attribution_endpoint(req: AttributionRequest, db: Session = Depends(get_db)):
    """Per-symbol P&L attribution, Sortino, Calmar for a backtest run."""
    from engine.analytics import match_trades_fifo, calculate_sortino_ratio, calculate_calmar_ratio, portfolio_attribution

    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == req.run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    from backend.routers.backtest import get_backtest_logs
    events = get_backtest_logs(req.run_id, db)
    raw_trades: list = []
    equity_curve: list = []
    for ev in events:
        raw_trades.extend(ev.get("orders_filled", []))

    # Equity curve from backtest result
    try:
        import json as _json
        eq_raw = r.equity_curve
        if isinstance(eq_raw, str):
            equity_curve = _json.loads(eq_raw)
        elif isinstance(eq_raw, list):
            equity_curve = eq_raw
    except Exception:
        equity_curve = []

    matched = match_trades_fifo(raw_trades)
    attribution = portfolio_attribution(matched)
    sortino = calculate_sortino_ratio(equity_curve)
    calmar = calculate_calmar_ratio(equity_curve)

    return {
        **attribution,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
    }


# ---------------------------------------------------------------------------
# Research extras: seasonality, volume profile, S/R
# ---------------------------------------------------------------------------

class ExtrasRequest(BaseModel):
    symbol: str
    interval: str


@router.post("/extras/seasonality")
def seasonality_endpoint(req: ExtrasRequest):
    """Seasonality analysis: day-of-week and month-of-year effects."""
    from engine.research_extras import seasonality_analysis
    client = SmartAPIClient()
    df = client.load_dataset_csv(req.symbol.upper(), req.interval.upper())
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return seasonality_analysis(df)


@router.post("/extras/volume-profile")
def volume_profile_endpoint(req: ExtrasRequest):
    """Volume profile: POC, VAH, VAL."""
    from engine.research_extras import volume_profile
    client = SmartAPIClient()
    df = client.load_dataset_csv(req.symbol.upper(), req.interval.upper())
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return volume_profile(df)


@router.post("/extras/support-resistance")
def sr_endpoint(req: ExtrasRequest):
    """Support and resistance level detection."""
    from engine.research_extras import detect_support_resistance
    client = SmartAPIClient()
    df = client.load_dataset_csv(req.symbol.upper(), req.interval.upper())
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return detect_support_resistance(df)
