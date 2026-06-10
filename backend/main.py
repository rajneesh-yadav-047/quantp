import os
import json
import uuid
import time
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, cast
from datetime import datetime, timezone, timedelta
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import init_db, get_db, StrategyDB, BacktestResultDB
from backend.smartapi import SmartAPIClient
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics
from engine.research import attribute_performance_by_regime
from engine.capital import analyze_capital_requirements
from engine.optimization import run_parameter_sweep

# Global instance for the sole user
global_smart_client: Optional[SmartAPIClient] = None

# Global symbols cache for autocomplete suggestions
symbol_suggestions: List[Dict[str, str]] = []

# Global state to track the active feed across sessions
active_feed_key: Optional[str] = None

def load_symbol_suggestions():
    global symbol_suggestions
    token_path = os.path.join("./datasets", "symbol_tokens.json")
    if os.path.exists(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                tokens = json.load(f)
            seen = set()
            temp = []
            for item in tokens:
                exch = item.get("exch_seg")
                inst_type = item.get("instrumenttype", "")
                if exch in ("NSE", "NFO", "MCX", "BSE", "CDS", "BFO", "NCDEX", "NCO"):
                    # Exclude option contracts to keep the catalog compact and relevant
                    if not inst_type.startswith("OPT"):
                        symbol = item.get("symbol")
                        name = item.get("name")
                        token = item.get("token")
                        if symbol:
                            sym_key = f"{exch}:{symbol}"
                            if sym_key not in seen:
                                seen.add(sym_key)
                                temp.append({
                                    "symbol": sym_key,
                                    "name": f"{name} ({exch} - {inst_type or 'EQUITY'})",
                                    "token": token
                                })
            symbol_suggestions = temp
            print(f"INFO: Loaded {len(symbol_suggestions)} symbol suggestions into memory.")
        except Exception as e:
            print(f"ERROR: Failed to load symbol suggestions: {e}")

# Lifespan context manager for startup and shutdown logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Initializing Database...")
    init_db()
    print("INFO: Database Initialization Complete.")
    print("INFO: Loading symbol suggestions...")
    load_symbol_suggestions()
    yield

# Initialize FastAPI App
app = FastAPI(title="QuantLab Backend", version="1.0.0", lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Debug middleware to log every request
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now(timezone.utc)
    print(f"DEBUG: {request.method} {request.url.path} - Processing...")
    response = await call_next(request)
    process_time = (datetime.now(timezone.utc) - start_time).total_seconds()
    print(f"DEBUG: {request.method} {request.url.path} - Completed in {process_time:.4f}s with Status {response.status_code}")
    return response

# Health Check Endpoint for diagnostics
@app.get("/api/health")
def health_check():
    return {"status": "online", "timestamp": datetime.now(timezone.utc).isoformat()}

# Pydantic Schemas for Requests
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
    runtime_type: Optional[str] = "legacy_on_bar"  # NEW: "legacy_on_bar" or "prosperity_trader"
    entrypoint: Optional[str] = None  # NEW: e.g. "trader.py:Trader"

class BacktestRequest(BaseModel):
    strategy_id: str
    symbols: List[str]  # Multiple symbols: ["SBIN", "RELIANCE"]
    interval: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    slippage_pct: float = 0.0005
    trade_type: str = "INTRADAY"
    max_position_size: Optional[int] = None
    runtime_type: Optional[str] = "legacy_on_bar"
    auto_download: bool = True  # Auto-download missing datasets

class OptimizationRequest(BaseModel):
    strategy_id: str
    symbol: str
    interval: str
    start_date: str
    end_date: str
    param_grid_json: str  # JSON string of ranges: e.g. {"ema_fast": [5,10], "ema_slow": [20,30]}
    initial_capital: float = 100000.0
    trade_type: str = "INTRADAY"

class SmartAPIConnectRequest(BaseModel):
    totp: str



@app.get("/api/auth/smartapi/status")
def smartapi_status():
    api_key = os.getenv("SMARTAPI_API_KEY")
    client_code = os.getenv("SMARTAPI_CLIENT_CODE")
    password = os.getenv("SMARTAPI_PASSWORD")
    
    configured = bool(api_key and client_code and password)
    
    # Check if the global client is connected
    connected = False
    if global_smart_client and global_smart_client.jwt_token and global_smart_client.is_configured():
        connected = True
        
    return {
        "configured": configured,
        "connected": connected,
        "client_code": client_code if configured else None
    }

@app.post("/api/auth/smartapi/connect")
def smartapi_connect(req: SmartAPIConnectRequest):
    global global_smart_client
    
    api_key = os.getenv("SMARTAPI_API_KEY")
    client_code = os.getenv("SMARTAPI_CLIENT_CODE")
    password = os.getenv("SMARTAPI_PASSWORD")
    
    if not (api_key and client_code and password):
        raise HTTPException(status_code=400, detail="SmartAPI credentials missing in .env file.")
        
    client = SmartAPIClient(
        api_key=api_key,
        client_code=client_code,
        password=password
    )
    
    success = client.connect(totp=req.totp)
    if success:
        global_smart_client = client
        return {"connection_success": True, "message": "Connected successfully"}
    else:
        return {"connection_success": False, "message": client.last_error}

# --- DATA STORAGE & DOWNLOAD ENDPOINTS ---

@app.post("/api/data/download")
def download_data(req: DownloadDataRequest):
    global global_smart_client, active_feed_key
    
    # Use existing client if already authenticated
    client = global_smart_client if global_smart_client and global_smart_client.jwt_token else SmartAPIClient(
        api_key=os.getenv("SMARTAPI_API_KEY"),
        client_code=os.getenv("SMARTAPI_CLIENT_CODE"),
        password=os.getenv("SMARTAPI_PASSWORD")
    )
    
    if not client.is_configured():
        raise HTTPException(status_code=400, detail="SmartAPI credentials not configured in .env file.")
        
    # Connect if not already authenticated or if TOTP provided for refresh
    if req.totp or not client.jwt_token:
        if not req.totp:
            raise HTTPException(status_code=400, detail="TOTP required for SmartAPI authentication.")
        if not client.connect(totp=req.totp):
            raise HTTPException(status_code=400, detail=f"SmartAPI login failed: {client.last_error}")
        global_smart_client = client
            
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
    
    # Mark this as the active feed immediately
    active_feed_key = key
    
    return {
        "message": "Dataset downloaded and cataloged successfully.",
        "details": catalog.get(key, {}),
        "active_feed": key,
        "catalog": catalog # Returning full catalog ensures the list updates in the UI
    }

@app.get("/api/data/datasets")
def list_datasets():
    client = SmartAPIClient()
    return client.load_catalog()

@app.get("/api/data/active")
def get_active_feed():
    return {"active_feed_key": active_feed_key}

@app.post("/api/data/active")
def set_active_feed(req: Dict[str, str]):
    global active_feed_key
    active_feed_key = req.get("key")
    return {"status": "success", "active_feed_key": active_feed_key}

@app.get("/api/data/symbols/search")
def search_symbols(q: str):
    if not q:
        return []
    query = q.upper()
    
    # Priority 1: Exact matches
    # Priority 2: Starts with matches
    # Priority 3: Contains matches
    p1, p2, p3 = [], [], []
    for item in symbol_suggestions:
        sym = item["symbol"].upper()
        name = item["name"].upper()
        tok = item["token"]
        
        if query == sym or query == name or query == tok:
            p1.append(item)
        elif sym.startswith(query) or name.startswith(query):
            p2.append(item)
        elif query in sym or query in name:
            p3.append(item)
            
    # Sort matches by symbol length to prioritize shorter/cleaner symbols
    p1.sort(key=lambda x: len(x["symbol"]))
    p2.sort(key=lambda x: len(x["symbol"]))
    p3.sort(key=lambda x: len(x["symbol"]))
    
    combined = (p1 + p2 + p3)[:15]
    return combined

@app.get("/api/data/datasets/{symbol}/{interval}")
def get_dataset(symbol: str, interval: str):
    client = SmartAPIClient()
    df = client.load_dataset_parquet(symbol, interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Dataset not found or empty.")
        
    # Format time column for Lightweight Charts compatibility
    # Intraday data requires Unix timestamps (seconds), Daily data requires YYYY-MM-DD
    try:
        # Convert the time column to datetime objects to ensure clean formatting
        times = pd.to_datetime(df['time'])
        
        if interval.upper() == "ONE_DAY":
            # Daily bars: Lightweight Charts expects "YYYY-MM-DD"
            df['time'] = times.dt.strftime('%Y-%m-%d')
        else:
            # Intraday bars: Lightweight Charts expects Unix timestamp (integer seconds)
            df['time'] = times.apply(lambda x: int(x.timestamp()))
    except Exception as e:
        print(f"DEBUG: Date formatting error for {symbol}: {e}")

    # Calculate a suggested max position size using risk-based sizing
    avg_price = float(df['close'].iloc[-100:].mean()) if not df.empty else 0
    price_std = float(df['close'].iloc[-100:].std()) if len(df) > 1 else avg_price * 0.02
    
    risk_pct = 0.02  # 2% risk per trade
    risk_amount = 100000 * risk_pct  # Default 1L capital
    stop_distance = max(price_std * 2, avg_price * 0.005)
    risk_based_size = int(risk_amount / stop_distance) if stop_distance > 0 else 1
    
    margin_based_size = int(100000 * 5 / avg_price) if avg_price > 0 else 1  # INTRADAY 5x
    suggested_max_pos = min(risk_based_size, int(margin_based_size * 0.20))
    suggested_max_pos = max(suggested_max_pos, 1)

    # Return first 2000 rows as list of dicts for safety of JSON size
    data = df.to_dict(orient="records")
    return {
        "symbol": symbol.upper(),
        "interval": interval.upper(),
        "total_records": len(df),
        "suggested_max_position": suggested_max_pos,
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
        "runtime_type": getattr(s, 'runtime_type', 'legacy_on_bar'),
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
        "runtime_type": getattr(s, 'runtime_type', 'legacy_on_bar'),
        "entrypoint": getattr(s, 'entrypoint', None),
        "version": s.version,
        "updated_at": s.updated_at
    }

@app.post("/api/strategies")
def create_strategy(req: StrategyCreateRequest, db: Session = Depends(get_db)):
    s = StrategyDB(
        name=req.name,
        description=req.description,
        code=req.code,
        runtime_type=req.runtime_type or "legacy_on_bar",
        entrypoint=req.entrypoint,
        version=1
    )
    db.add(s)
    db.commit()
    return {"message": "Strategy created successfully", "id": s.id, "runtime_type": s.runtime_type}

@app.put("/api/strategies/{strategy_id}")
def update_strategy(strategy_id: str, req: StrategyCreateRequest, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    setattr(s, 'name', req.name)
    setattr(s, 'description', req.description)
    setattr(s, 'code', req.code)
    setattr(s, 'runtime_type', req.runtime_type or "legacy_on_bar")
    setattr(s, 'entrypoint', req.entrypoint)
    setattr(s, 'version', cast(int, s.version) + 1)
    setattr(s, 'updated_at', datetime.now(timezone.utc))
    
    db.commit()
    return {"message": "Strategy updated successfully", "id": s.id, "version": s.version, "runtime_type": s.runtime_type}

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

    # 2. Fetch / Auto-download Parquet Data for ALL symbols
    client = SmartAPIClient()
    df_dict: Dict[str, pd.DataFrame] = {}
    downloaded_symbols = []
    
    # Prepare a single shared download client to avoid re-authenticating per symbol
    dl_client: Optional[SmartAPIClient] = None
    if req.auto_download:
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        if api_key and client_code and password:
            dl_client = SmartAPIClient(api_key=api_key, client_code=client_code, password=password)
            if not dl_client.connect():
                print(f"WARN: Shared SmartAPI connect failed: {dl_client.last_error}")
                dl_client = None
    
    for symbol in req.symbols:
        sym = symbol.upper().strip()
        if not sym:
            continue
            
        df = client.load_dataset_parquet(sym, req.interval)
        
        # Auto-download if missing and enabled
        if (df is None or df.empty) and req.auto_download and dl_client is not None:
            try:
                df = dl_client.fetch_historical_candles(
                    symbol=sym,
                    from_date=req.start_date + " 09:15",
                    to_date=req.end_date + " 15:30",
                    interval=req.interval
                )
                if not df.empty:
                    dl_client.save_dataset_parquet(sym, req.interval, df)
                    downloaded_symbols.append(sym)
                    # Small delay between serial downloads to avoid rate-limiting
                    time.sleep(0.5)
            except Exception as e:
                print(f"WARN: Auto-download failed for {sym}: {e}")
        
        # If still empty, generate mock data
        if df is None or df.empty:
            df = client.generate_mock_candles(sym, req.start_date, req.end_date, req.interval)
            if not df.empty:
                client.save_dataset_parquet(sym, req.interval, df)
                downloaded_symbols.append(f"{sym}(mock)")
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data available for {sym} ({req.interval}). Download failed or not configured.")
        
        # Slice date range
        try:
            time_series = pd.to_datetime(df['time'])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Date parsing error in {sym} data: {str(e)}")
            
        if time_series.dt.tz is not None:
            df['time_dt'] = time_series.dt.tz_localize(None)
        else:
            df['time_dt'] = time_series
            
        try:
            start_dt = pd.to_datetime(req.start_date, format='%Y-%m-%d', errors='raise')
        except Exception:
            # Fallback: try flexible parsing
            start_dt = pd.to_datetime(req.start_date, dayfirst=True, errors='coerce')
            if pd.isna(start_dt):
                raise HTTPException(status_code=400, detail=f"Invalid start_date format: '{req.start_date}'. Expected YYYY-MM-DD.")
                
        try:
            end_dt = pd.to_datetime(req.end_date, format='%Y-%m-%d', errors='raise')
        except Exception:
            end_dt = pd.to_datetime(req.end_date, dayfirst=True, errors='coerce')
            if pd.isna(end_dt):
                raise HTTPException(status_code=400, detail=f"Invalid end_date format: '{req.end_date}'. Expected YYYY-MM-DD.")
            
        if len(req.end_date.strip()) <= 10:
            end_dt = end_dt + pd.Timedelta(hours=23, minutes=59, seconds=59)
        df = df[(df['time_dt'] >= start_dt) & (df['time_dt'] <= end_dt)]
        
        # Clean data
        df = df.ffill().bfill()
        
        if not df.empty:
            df_dict[sym] = df.drop(columns=['time_dt'])
    
    if not df_dict:
        raise HTTPException(status_code=400, detail="No valid data found for any symbol in the requested date range.")

    # Calculate max position size using the first symbol's volatility
    first_df = list(df_dict.values())[0]
    avg_price = float(first_df['close'].mean())
    price_std = float(first_df['close'].std()) if len(first_df) > 1 else avg_price * 0.02
    
    risk_pct = 0.02
    risk_amount = req.initial_capital * risk_pct
    stop_distance = max(price_std * 2, avg_price * 0.005)
    risk_based_size = int(risk_amount / stop_distance) if stop_distance > 0 else 1
    
    margin_mult = 0.20 if req.trade_type == "INTRADAY" else (0.15 if req.trade_type == "FUTURES" else 1.0)
    leverage = 1.0 / margin_mult if margin_mult > 0 else 1.0
    margin_based_size = int(req.initial_capital * leverage / avg_price) if avg_price > 0 else 1
    
    auto_max_pos = min(risk_based_size, int(margin_based_size * 0.20))
    auto_max_pos = max(auto_max_pos, 1)
    
    final_max_pos = req.max_position_size if (req.max_position_size and req.max_position_size > 0) else auto_max_pos

    try:
        # 3. Instantiate engine and run backtest
        run_id = f"B-{uuid.uuid4().hex[:8].upper()}"
        
        engine = BacktestEngine(
            df_dict=df_dict,
            strategy_code=cast(str, s.code),
            initial_capital=req.initial_capital,
            slippage_pct=req.slippage_pct,
            default_trade_type=req.trade_type,
            max_position_size=final_max_pos,
            runtime_type=getattr(s, 'runtime_type', 'legacy_on_bar'),
        )
        res = engine.run(run_id=run_id)

        # 4. Process analytics metrics
        metrics = calculate_metrics(res['equity_curve'], res['trades'], req.initial_capital)
        metrics['equity_curve'] = res['equity_curve']
        
        # 5. Catalog the results in database
        primary_symbol = req.symbols[0].upper() if req.symbols else "MULTI"
        result = BacktestResultDB(
            id=run_id,
            strategy_id=s.id,
            strategy_name=s.name,
            symbol=primary_symbol,
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
            max_position_size=final_max_pos,
            log_file_path=res['log_file_path'],
            metrics_json=cast(str, json.dumps(metrics))
        )
        
        db.add(result)
        db.commit()

        return {
            "run_id": run_id,
            "metrics": metrics,
            "equity_curve": res['equity_curve'],
            "final_equity": res['final_portfolio']['equity'],
            "downloaded_symbols": downloaded_symbols,
            "symbols_used": list(df_dict.keys())
        }

    except Exception as e:
        print(f"CRITICAL BACKTEST ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backtest Engine Failure: {str(e)}")

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
        "max_position_size": r.max_position_size,
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
        "metrics": json.loads(cast(str, r.metrics_json)),
        "created_at": r.created_at
    }

@app.get("/api/backtest/logs/{run_id}")
def get_backtest_logs(run_id: str, db: Session = Depends(get_db)):
    """
    Get replay events for a backtest run.
    Returns structured JSONL events with strategy logs, trades, and portfolio state.
    """
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
        
    if not os.path.exists(cast(str, r.log_file_path)):
        raise HTTPException(status_code=404, detail="Log file missing on disk")
        
    events = []
    with open(cast(str, r.log_file_path), "r") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                # Parse strategy_logs if it's a JSON string
                if isinstance(event.get('strategy_logs'), str):
                    try:
                        event['strategy_logs'] = json.loads(event['strategy_logs'])
                    except json.JSONDecodeError:
                        event['strategy_logs'] = []
                events.append(event)
            except json.JSONDecodeError:
                pass  # Skip malformed lines
            
    return events

# --- RESEARCH LAB (REGIME ATTRIBUTION) ---

@app.get("/api/research/regimes/{run_id}")
def get_regime_attribution(run_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestResultDB).filter(BacktestResultDB.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest run not found")
        
    client = SmartAPIClient()
    df = client.load_dataset_parquet(cast(str, r.symbol), cast(str, r.interval))
    if df is None:
        raise HTTPException(status_code=404, detail="Original Parquet dataset missing from catalog.")
        
    # Read the logs to reconstruct trades list
    events = get_backtest_logs(run_id, db)
    trades = []
    for ev in events:
        trades.extend(ev.get('orders_filled', []))
        
    attribution = attribute_performance_by_regime({cast(str, r.symbol): df}, trades)
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
    df = client.load_dataset_parquet(cast(str, r.symbol), cast(str, r.interval))
    if df is None:
        raise HTTPException(status_code=404, detail="Parquet dataset not found.")
        
    # Filter dates
    time_series = pd.to_datetime(df['time'])
    if time_series.dt.tz is not None:
        df['time_dt'] = time_series.dt.tz_localize(None)
    else:
        df['time_dt'] = time_series
        
    start_dt = pd.to_datetime(cast(str, r.start_time))
    if start_dt.tz is not None:
        start_dt = start_dt.tz_localize(None)
        
    end_dt = pd.to_datetime(cast(str, r.end_time))
    if end_dt.tz is not None:
        end_dt = end_dt.tz_localize(None)
        
    if len(r.end_time.strip()) <= 10:
        end_dt = end_dt + pd.Timedelta(hours=23, minutes=59, seconds=59)
    df = df[(df['time_dt'] >= start_dt) & (df['time_dt'] <= end_dt)]
    df_dict = {cast(str, r.symbol): df.drop(columns=['time_dt'])}
    
    # Run multi-pass capital simulations
    analysis = analyze_capital_requirements(
        df_dict=df_dict,
        strategy_code=cast(str, s.code),
        default_trade_type=cast(str, r.interval)
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
        
    time_series = pd.to_datetime(df['time'])
    if time_series.dt.tz is not None:
        df['time_dt'] = time_series.dt.tz_localize(None)
    else:
        df['time_dt'] = time_series
        
    start_dt = pd.to_datetime(req.start_date)
    if start_dt.tz is not None:
        start_dt = start_dt.tz_localize(None)
        
    end_dt = pd.to_datetime(req.end_date)
    if end_dt.tz is not None:
        end_dt = end_dt.tz_localize(None)
        
    if len(req.end_date.strip()) <= 10:
        end_dt = end_dt + pd.Timedelta(hours=23, minutes=59, seconds=59)
    df = df[(df['time_dt'] >= start_dt) & (df['time_dt'] <= end_dt)]
    df_dict = {req.symbol.upper(): df.drop(columns=['time_dt'])}
    
    try:
        param_grid = json.loads(req.param_grid_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid param_grid_json string.")
        
    sweep_results = run_parameter_sweep(
        df_dict=df_dict,
        strategy_code=cast(str, s.code),
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
