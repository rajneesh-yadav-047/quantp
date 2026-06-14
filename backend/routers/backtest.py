"""
Backtest router: backtest execution, results, logs.
"""

import os
import json
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db, StrategyDB, BacktestResultDB
from backend.services.data_service import prepare_backtest_data
from backend.services.sizing_service import calculate_backtest_max_position
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    strategy_id: str
    symbols: Optional[List[str]] = None  # Override strategy symbols if provided
    interval: Optional[str] = None  # Override strategy interval if provided
    start_date: str
    end_date: str
    initial_capital: Optional[float] = None  # Override strategy capital if provided
    slippage_pct: float = 0.0005
    trade_type: str = "INTRADAY"
    max_position_size: Optional[int] = None  # Override strategy max_position if provided
    runtime_type: Optional[str] = None
    auto_download: bool = True


class OptimizationRequest(BaseModel):
    strategy_id: str
    symbol: str
    interval: str
    start_date: str
    end_date: str
    param_grid_json: str
    initial_capital: float = 100000.0
    trade_type: str = "INTRADAY"


@router.post("/run")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    # 1. Fetch Strategy
    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # 2. Resolve config from strategy or request overrides
    symbols = req.symbols if req.symbols is not None else (json.loads(s.symbols) if s.symbols else ["SBIN"])
    interval = req.interval if req.interval is not None else (s.interval or "FIVE_MINUTE")
    initial_capital = req.initial_capital if req.initial_capital is not None else (s.initial_capital or 100000.0)
    max_position_size = req.max_position_size if req.max_position_size is not None else s.max_position_size
    runtime_type = req.runtime_type if req.runtime_type is not None else getattr(s, 'runtime_type', 'legacy_on_bar')
    parameters = json.loads(s.parameters_json) if s.parameters_json else None

    # 3. Prepare data for all symbols
    df_dict, downloaded_symbols, failed_symbols = prepare_backtest_data(
        symbols=symbols,
        interval=interval,
        start_date=req.start_date,
        end_date=req.end_date,
        auto_download=req.auto_download,
    )

    if not df_dict:
        raise HTTPException(status_code=400, detail="No valid data found for any symbol in the requested date range.")
    if failed_symbols:
        print(f"WARN: Failed to load data for: {failed_symbols}")

    # 4. Calculate max position size
    first_df = list(df_dict.values())[0]
    final_max_pos = calculate_backtest_max_position(
        df=first_df,
        initial_capital=initial_capital,
        trade_type=req.trade_type,
        requested_max=max_position_size,
    )

    # 5. Run backtest
    try:
        run_id = f"B-{uuid.uuid4().hex[:8].upper()}"
        engine = BacktestEngine(
            df_dict=df_dict,
            strategy_code=s.code or "",
            initial_capital=initial_capital,
            slippage_pct=req.slippage_pct,
            default_trade_type=req.trade_type,
            max_position_size=final_max_pos,
            runtime_type=runtime_type,
            parameters=parameters,
        )
        res = engine.run(run_id=run_id)

        # 6. Analytics
        metrics = calculate_metrics(res['equity_curve'], res['trades'], initial_capital)
        metrics['equity_curve'] = res['equity_curve']

        # 7. Catalog result
        primary_symbol = symbols[0].upper() if symbols else "MULTI"
        result = BacktestResultDB(
            id=run_id,
            strategy_id=s.id,
            strategy_name=s.name,
            symbol=primary_symbol,
            symbols_json=json.dumps(symbols),
            interval=interval.upper(),
            start_time=req.start_date,
            end_time=req.end_date,
            initial_capital=initial_capital,
            final_equity=res['final_portfolio']['equity'],
            total_pnl=metrics.get("total_pnl", 0.0),
            cagr=metrics.get("cagr", 0.0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
            sortino_ratio=metrics.get("sortino_ratio", 0.0),
            max_drawdown=metrics.get("max_drawdown", 0.0),
            win_rate=metrics.get("win_rate", 0.0),
            profit_factor=metrics.get("profit_factor", 0.0),
            total_fees=metrics.get("cost_breakdown", {}).get("total_fees", 0.0),
            max_position_size=final_max_pos,
            log_file_path=res['log_file_path'],
            metrics_json=json.dumps(metrics),
        )
        db.add(result)
        db.commit()

        return {
            "run_id": run_id,
            "metrics": metrics,
            "equity_curve": res['equity_curve'],
            "final_equity": res['final_portfolio']['equity'],
            "downloaded_symbols": downloaded_symbols,
            "symbols_used": list(df_dict.keys()),
        }

    except Exception as e:
        print(f"CRITICAL BACKTEST ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backtest Engine Failure: {str(e)}")


@router.get("/results")
def list_backtest_results(db: Session = Depends(get_db)):
    results = db.query(BacktestResultDB).order_by(BacktestResultDB.created_at.desc()).all()
    valid_results = []
    for r in results:
        if r.log_file_path and os.path.exists(r.log_file_path):
            valid_results.append(r)
    return [{
        "id": r.id,
        "strategy_name": r.strategy_name,
        "symbol": r.symbol,
        "symbols": json.loads(r.symbols_json) if r.symbols_json else [r.symbol],
        "interval": r.interval,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "total_pnl": r.total_pnl,
        "cagr": r.cagr,
        "sharpe_ratio": r.sharpe_ratio,
        "max_drawdown": r.max_drawdown,
        "max_position_size": r.max_position_size,
        "created_at": r.created_at,
    } for r in valid_results]


@router.get("/results/{run_id}")
def get_backtest_result(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    
    # Extract trades from the log file
    trades = []
    if r.log_file_path and os.path.exists(r.log_file_path):
        with open(r.log_file_path, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    filled = event.get("orders_filled", [])
                    if filled:
                        trades.extend(filled)
                except (json.JSONDecodeError, Exception):
                    pass
    
    return {
        "id": r.id,
        "strategy_id": r.strategy_id,
        "strategy_name": r.strategy_name,
        "symbol": r.symbol,
        "symbols": json.loads(r.symbols_json) if r.symbols_json else [r.symbol],
        "interval": r.interval,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "initial_capital": r.initial_capital,
        "final_equity": r.final_equity,
        "total_pnl": r.total_pnl,
        "cagr": r.cagr,
        "sharpe_ratio": r.sharpe_ratio,
        "sortino_ratio": r.sortino_ratio,
        "max_drawdown": r.max_drawdown,
        "win_rate": r.win_rate,
        "profit_factor": r.profit_factor,
        "total_fees": r.total_fees,
        "metrics": json.loads(r.metrics_json or "{}"),
        "trades": trades,
        "trade_count": len(trades),
        "created_at": r.created_at,
    }


@router.get("/logs/{run_id}")
def get_backtest_logs(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    if not r.log_file_path or not os.path.exists(r.log_file_path):
        raise HTTPException(status_code=404, detail="Log file missing on disk")

    events = []
    with open(r.log_file_path, "r") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                if isinstance(event.get('strategy_logs'), str):
                    try:
                        event['strategy_logs'] = json.loads(event['strategy_logs'])
                    except json.JSONDecodeError:
                        event['strategy_logs'] = []
                events.append(event)
            except json.JSONDecodeError:
                pass
    return events
