"""
Research router: regime attribution, capital analysis, optimization,
AND independent dataset deep analysis.
"""

import json
from typing import cast, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db, BacktestResultDB, StrategyDB
from backend.smartapi import SmartAPIClient
from backend.services.data_service import slice_dataframe_by_date
from engine.research import attribute_performance_by_regime
from engine.capital import analyze_capital_requirements
from engine.optimization import run_parameter_sweep
from engine.data_analyzer import analyze_dataset

router = APIRouter(prefix="/api/research", tags=["research"])


class DatasetAnalysisRequest(BaseModel):
    symbol: str
    interval: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/analyze")
def analyze_dataset_endpoint(req: DatasetAnalysisRequest):
    """
    Deep statistical analysis of a dataset — completely independent of backtest results.
    """
    client = SmartAPIClient()
    lookup_key = f"{req.symbol.upper()}_{req.interval.upper()}"
    catalog = client.load_catalog()
    print(f"DEBUG research/analyze: looking for key={lookup_key}, catalog_keys={list(catalog.keys())}")
    
    df = client.load_dataset_csv(req.symbol.upper(), req.interval.upper())
    if df is None:
        print(f"DEBUG research/analyze: df is None for key={lookup_key}")
        raise HTTPException(status_code=404, detail=f"Dataset not found in catalog. (looked for: {lookup_key}, available: {list(catalog.keys())})")
    if df.empty:
        print(f"DEBUG research/analyze: df is empty for key={lookup_key}")
        raise HTTPException(status_code=404, detail="Dataset empty after loading.")

    # Optional date slice
    if req.start_date and req.end_date:
        try:
            df = slice_dataframe_by_date(df, req.start_date, req.end_date)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Date slicing error: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset empty after date filtering.")

    result = analyze_dataset(
        df=df,
        symbol=req.symbol.upper(),
        interval=req.interval.upper(),
    )
    return result


@router.get("/regimes/{run_id}")
def get_regime_attribution(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    client = SmartAPIClient()
    df = client.load_dataset_csv(cast(str, r.symbol), cast(str, r.interval))
    if df is None:
        raise HTTPException(status_code=404, detail="Original Parquet dataset missing from catalog.")

    # Read logs to reconstruct trades
    from backend.routers.backtest import get_backtest_logs
    events = get_backtest_logs(run_id, db)
    trades = []
    for ev in events:
        trades.extend(ev.get('orders_filled', []))

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
        raise HTTPException(status_code=404, detail="Parquet dataset not found.")

    df = slice_dataframe_by_date(df, cast(str, r.start_time), cast(str, r.end_time))
    df_dict = {cast(str, r.symbol): df}

    analysis = analyze_capital_requirements(
        df_dict=df_dict,
        strategy_code=cast(str, s.code),
        default_trade_type=cast(str, r.interval),
    )
    return analysis


class OptimizationRequest(BaseModel):
    strategy_id: str
    symbol: str
    interval: str
    start_date: str
    end_date: str
    param_grid_json: str
    initial_capital: float = 100000.0
    trade_type: str = "INTRADAY"


@router.post("/optimize")
def run_optimization(req: OptimizationRequest, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    client = SmartAPIClient()
    df = client.load_dataset_csv(req.symbol, req.interval)
    if df is None:
        raise HTTPException(status_code=404, detail="Parquet dataset not found.")

    df = slice_dataframe_by_date(df, req.start_date, req.end_date)
    df_dict = {req.symbol.upper(): df}

    try:
        param_grid = json.loads(req.param_grid_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid param_grid_json string.")

    sweep_results = run_parameter_sweep(
        df_dict=df_dict,
        strategy_code=cast(str, s.code),
        param_grid=param_grid,
        initial_capital=req.initial_capital,
        default_trade_type=req.trade_type,
    )
    return sweep_results
