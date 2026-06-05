import os
import json
import uuid
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import init_db, get_db, UserDB, StrategyDB, BacktestResultDB
from backend.smartapi import SmartAPIClient
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics
from engine.research import attribute_performance_by_regime
from engine.capital import analyze_capital_requirements
from engine.optimization import run_parameter_sweep

# Lifespan context manager for startup and shutdown logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Initializing Database...")
    init_db()
    print("INFO: Database Initialization Complete.")
    yield

# Initialize FastAPI App
app = FastAPI(title="QuantLab Backend", version="1.0.0", lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Debug middleware to log every request
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.utcnow()
    print(f"DEBUG: {request.method} {request.url.path} - Processing...")
    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds()
    print(f"DEBUG: {request.method} {request.url.path} - Completed in {process_time:.4f}s with Status {response.status_code}")
    return response

# Health Check Endpoint for diagnostics
@app.get("/api/health")
def health_check():
    return {"status": "online", "timestamp": datetime.utcnow().isoformat()}

# Pydantic Schemas for Requests
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class SmartAPICredsRequest(BaseModel):
    username: str  # DB user association
    api_key: str
    client_code: str
    password: str
    totp_secret: Optional[str] = None
    totp: Optional[str] = None
    remember_me: bool = True

class DownloadDataRequest(BaseModel):
    symbol: str
    interval: str
    from_date: str  # YYYY-MM-DD
    to_date: str    # YYYY-MM-DD
    totp: Optional[str] = None

class StrategyCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    code: str

class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    interval: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    slippage_pct: float = 0.0005
    trade_type: str = "INTRADAY"

class OptimizationRequest(BaseModel):
    strategy_id: str
    symbol: str
    interval: str
    start_date: str
    end_date: str
    param_grid_json: str  # JSON string of ranges: e.g. {"ema_fast": [5,10], "ema_slow": [20,30]}
    initial_capital: float = 100000.0
    trade_type: str = "INTRADAY"

# --- AUTH & SMARTAPI BRIDGE ENDPOINTS ---

@app.post("/api/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # In production use bcrypt, plain hashes for simplicity of zero-config setup
    user = UserDB(username=req.username, password_hash=req.password)
    db.add(user)
    db.commit()
    return {"message": "Registration successful", "user_id": user.id}

@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == req.username).first()
    if not user or user.password_hash != req.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "message": "Login successful",
        "user_id": user.id,
        "smartapi_configured": bool(user.smartapi_api_key)
    }

@app.get("/api/auth/smartapi/env")
def get_smartapi_env():
    return {
        "client_code": os.getenv("SMARTAPI_CLIENT_CODE", ""),
        "password": os.getenv("SMARTAPI_PASSWORD", ""),
        "api_key": os.getenv("SMARTAPI_API_KEY", "")
    }

@app.post("/api/auth/smartapi/configure")
def configure_smartapi(req: SmartAPICredsRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.remember_me:
        user.smartapi_api_key = req.api_key
        user.smartapi_client_code = req.client_code
        user.smartapi_password = req.password
        user.smartapi_totp_secret = req.totp_secret
        db.commit()
    
    # Try connecting immediately to verify credentials
    client = SmartAPIClient(
        api_key=req.api_key,
        client_code=req.client_code,
        password=req.password,
        totp_secret=req.totp_secret
    )
    success = client.connect(totp=req.totp)
    
    return {
        "message": "Configuration updated" if req.remember_me else "Configuration validated",
        "connection_success": success,
        "remembered": req.remember_me
    }

@app.get("/api/auth/smartapi/status/{username}")
def smartapi_status(username: str, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    configured = bool(user.smartapi_api_key)
    connected = False
    
    if configured:
        client = SmartAPIClient(
            api_key=user.smartapi_api_key,
            client_code=user.smartapi_client_code,
            password=user.smartapi_password,
            totp_secret=user.smartapi_totp_secret
        )
        if user.smartapi_totp_secret:
            connected = client.connect()
        else:
            connected = False
        
    return {
        "configured": configured,
        "connected": connected,
        "client_code": user.smartapi_client_code if configured else None
    }

# --- DATA STORAGE & DOWNLOAD ENDPOINTS ---

@app.post("/api/data/download")
def download_data(req: DownloadDataRequest, username: Optional[str] = None, db: Session = Depends(get_db)):
    # Initialize client, use credentials from DB if provided, else run in Mock fallback
    client_args = {}
    if username:
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if user and user.smartapi_api_key:
            client_args = {
                "api_key": user.smartapi_api_key,
                "client_code": user.smartapi_client_code,
                "password": user.smartapi_password,
                "totp_secret": user.smartapi_totp_secret
            }
            
    client = SmartAPIClient(**client_args)
    if not client.is_configured():
        raise HTTPException(status_code=400, detail="SmartAPI credentials not configured.")
    if not client.totp_secret and not req.totp:
        raise HTTPException(status_code=400, detail="TOTP required to authenticate SmartAPI.")
    client.connect(totp=req.totp)
    
    df = client.fetch_historical_candles(
        symbol=req.symbol,
        from_date=req.from_date,
        to_date=req.to_date,
        interval=req.interval
    )
    
    if df.empty:
        raise HTTPException(status_code=400, detail="No historical data returned from SmartAPI/Mock Generator.")
        
    file_path = client.save_dataset_parquet(req.symbol, req.interval, df)
    
    # Reload catalog index
    catalog = client.load_catalog()
    key = f"{req.symbol.upper()}_{req.interval.upper()}"
    
    return {
        "message": "Dataset downloaded and cataloged successfully.",
        "details": catalog.get(key, {})
    }

@app.get("/api/data/datasets")
def list_datasets():
    client = SmartAPIClient()
    return client.load_catalog()

@app.get("/api/data/datasets/{symbol}/{interval}")
def get_dataset(symbol: str, interval: str):
    client = SmartAPIClient()
    df = client.load_dataset_parquet(symbol, interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Dataset not found or empty.")
        
    # Return first 2000 rows as list of dicts for safety of JSON size
    data = df.to_dict(orient="records")
    return {
        "symbol": symbol.upper(),
        "interval": interval.upper(),
        "total_records": len(df),
        "candles": data[:2000]  # Limit payload
    }

# --- STRATEGY IDE CRUD ENDPOINTS ---

@app.get("/api/strategies")
def list_strategies(db: Session = Depends(get_db)):
    strategies = db.query(StrategyDB).all()
    return [{
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "version": s.version,
        "updated_at": s.updated_at
    } for s in strategies]

@app.get("/api/strategies/{strategy_id}")
def get_strategy(strategy_id: str, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "code": s.code,
        "version": s.version,
        "updated_at": s.updated_at
    }

@app.post("/api/strategies")
def create_strategy(req: StrategyCreateRequest, db: Session = Depends(get_db)):
    s = StrategyDB(
        name=req.name,
        description=req.description,
        code=req.code,
        version=1
    )
    db.add(s)
    db.commit()
    return {"message": "Strategy created successfully", "id": s.id}

@app.put("/api/strategies/{strategy_id}")
def update_strategy(strategy_id: str, req: StrategyCreateRequest, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    s.name = req.name
    s.description = req.description
    s.code = req.code
    s.version += 1
    s.updated_at = datetime.utcnow()
    
    db.commit()
    return {"message": "Strategy updated successfully", "id": s.id, "version": s.version}

@app.delete("/api/strategies/{strategy_id}")
def delete_strategy(strategy_id: str, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    db.delete(s)
    db.commit()
    return {"message": "Strategy deleted successfully"}

# --- BACKTESTING, REPLAY LOGS & ANALYTICS ---

@app.post("/api/backtest/run")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    # 1. Fetch Strategy
    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # 2. Fetch Parquet Data
    client = SmartAPIClient()
    df = client.load_dataset_parquet(req.symbol, req.interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Parquet dataset not found for {req.symbol} ({req.interval}). Download it first.")

    # Slice date range
    df['time_dt'] = pd.to_datetime(df['time'])
    df = df[(df['time_dt'] >= pd.to_datetime(req.start_date)) & (df['time_dt'] <= pd.to_datetime(req.end_date))]
    
    if df.empty:
        raise HTTPException(status_code=400, detail="Target date range contains 0 candles.")

    # 3. Instantiate engine and run backtest
    run_id = f"B-{uuid.uuid4().hex[:8].upper()}"
    df_dict = {req.symbol.upper(): df.drop(columns=['time_dt'])}
    
    engine = BacktestEngine(
        df_dict=df_dict,
        strategy_code=s.code,
        initial_capital=req.initial_capital,
        slippage_pct=req.slippage_pct,
        default_trade_type=req.trade_type
    )

    try:
        res = engine.run(run_id=run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest Engine Failure: {str(e)}")

    # 4. Process analytics metrics
    metrics = calculate_metrics(res['equity_curve'], res['trades'], req.initial_capital)
    
    # 5. Catalog the results in database
    result = BacktestResultDB(
        id=run_id,
        strategy_id=s.id,
        strategy_name=s.name,
        symbol=req.symbol.upper(),
        interval=req.interval.upper(),
        start_time=req.start_date,
        end_time=req.end_date,
        initial_capital=req.initial_capital,
        final_equity=res['final_portfolio']['equity'],
        total_pnl=metrics.get("total_pnl", 0.0),
        cagr=metrics.get("cagr", 0.0),
        sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
        sortino_ratio=metrics.get("sortino_ratio", 0.0),
        max_drawdown=metrics.get("max_drawdown", 0.0),
        win_rate=metrics.get("win_rate", 0.0),
        profit_factor=metrics.get("profit_factor", 0.0),
        total_fees=metrics.get("cost_breakdown", {}).get("total_fees", 0.0),
        log_file_path=res['log_file_path'],
        metrics_json=json.dumps(metrics)
    )
    
    db.add(result)
    db.commit()

    return {
        "run_id": run_id,
        "metrics": metrics,
        "final_equity": res['final_portfolio']['equity']
    }

@app.get("/api/backtest/results")
def list_backtest_results(db: Session = Depends(get_db)):
    results = db.query(BacktestResultDB).order_by(BacktestResultDB.created_at.desc()).all()
    return [{
        "id": r.id,
        "strategy_name": r.strategy_name,
        "symbol": r.symbol,
        "interval": r.interval,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "total_pnl": r.total_pnl,
        "cagr": r.cagr,
        "sharpe_ratio": r.sharpe_ratio,
        "max_drawdown": r.max_drawdown,
        "created_at": r.created_at
    } for r in results]

@app.get("/api/backtest/results/{run_id}")
def get_backtest_result(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
        
    return {
        "id": r.id,
        "strategy_id": r.strategy_id,
        "strategy_name": r.strategy_name,
        "symbol": r.symbol,
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
        "metrics": json.loads(r.metrics_json),
        "created_at": r.created_at
    }

@app.get("/api/backtest/logs/{run_id}")
def get_backtest_logs(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
        
    if not os.path.exists(r.log_file_path):
        raise HTTPException(status_code=404, detail="Log file missing on disk")
        
    events = []
    with open(r.log_file_path, "r") as f:
        for line in f:
            events.append(json.loads(line.strip()))
            
    return events

# --- RESEARCH LAB (REGIME ATTRIBUTION) ---

@app.get("/api/research/regimes/{run_id}")
def get_regime_attribution(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
        
    client = SmartAPIClient()
    df = client.load_dataset_parquet(r.symbol, r.interval)
    if df is None:
        raise HTTPException(status_code=404, detail="Original Parquet dataset missing from catalog.")
        
    # Read the logs to reconstruct trades list
    events = get_backtest_logs(run_id, db)
    trades = []
    for ev in events:
        trades.extend(ev.get('orders_filled', []))
        
    attribution = attribute_performance_by_regime({r.symbol: df}, trades)
    return attribution

# --- CAPITAL STUDIO ---

@app.get("/api/capital/analysis/{run_id}")
def get_capital_analysis(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
        
    # Load Strategy code
    s = db.query(StrategyDB).filter(StrategyDB.id == r.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy script missing in DB.")
        
    client = SmartAPIClient()
    df = client.load_dataset_parquet(r.symbol, r.interval)
    if df is None:
        raise HTTPException(status_code=404, detail="Parquet dataset not found.")
        
    # Filter dates
    df['time_dt'] = pd.to_datetime(df['time'])
    df = df[(df['time_dt'] >= pd.to_datetime(r.start_time)) & (df['time_dt'] <= pd.to_datetime(r.end_time))]
    df_dict = {r.symbol: df.drop(columns=['time_dt'])}
    
    # Run multi-pass capital simulations
    analysis = analyze_capital_requirements(
        df_dict=df_dict,
        strategy_code=s.code,
        default_trade_type=r.interval
    )
    return analysis

# --- OPTIMIZATION LAB ---

@app.post("/api/backtest/optimize")
def run_optimization(req: OptimizationRequest, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    client = SmartAPIClient()
    df = client.load_dataset_parquet(req.symbol, req.interval)
    if df is None:
        raise HTTPException(status_code=404, detail="Parquet dataset not found.")
        
    df['time_dt'] = pd.to_datetime(df['time'])
    df = df[(df['time_dt'] >= pd.to_datetime(req.start_date)) & (df['time_dt'] <= pd.to_datetime(req.end_date))]
    df_dict = {req.symbol.upper(): df.drop(columns=['time_dt'])}
    
    try:
        param_grid = json.loads(req.param_grid_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid param_grid_json string.")
        
    sweep_results = run_parameter_sweep(
        df_dict=df_dict,
        strategy_code=s.code,
        param_grid=param_grid,
        initial_capital=req.initial_capital,
        default_trade_type=req.trade_type
    )
    
    return sweep_results

# Standard runner
if __name__ == "__main__":
    import uvicorn
    # Allow configuration via environment variables for flexibility
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    
    print(f"--- QuantLab Backend Starting on http://{host}:{port} ---")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
