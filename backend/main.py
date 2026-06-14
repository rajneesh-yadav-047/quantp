"""
QuantLab Backend - Slimmed main application.

All endpoint logic moved to dedicated routers:
- auth: SmartAPI authentication
- data: dataset download, catalog, search
- strategies: strategy CRUD
- backtest: backtest execution, results, logs
- research: regime attribution, capital analysis, optimization
- cleanup: cleanup utilities (from existing cleanup_api)
"""

import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env BEFORE any module reads os.getenv()
load_dotenv()

from backend.database import init_db
from backend.routers import auth, data, strategies, backtest, research, deployments, live_trading
from backend.routers import groups as groups_router
from backend.cleanup_api import router as cleanup_router
from backend.services.market_data_service import MarketDataService
from backend.services.redis_client import get_redis_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Initializing Database...")
    init_db()
    print("INFO: Database Initialization Complete.")
    print("INFO: Loading symbol suggestions...")
    data._load_symbol_suggestions()
    
    # Initialize Market Data Service if SmartAPI is configured
    print("INFO: Checking SmartAPI configuration for Market Data Service...")
    from backend.services.smartapi_manager import SmartAPIManager
    if SmartAPIManager.is_configured():
        mds = MarketDataService.get_instance()
        mds.start()
        print("INFO: Market Data Service started.")
    else:
        print("INFO: SmartAPI not configured. Market Data Service will start on-demand.")
    
    yield
    
    # Shutdown
    print("INFO: Shutting down Market Data Service...")
    mds = MarketDataService.get_instance()
    mds.stop()


app = FastAPI(title="QuantLab Backend", version="2.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Debug middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now(timezone.utc)
    print(f"DEBUG: {request.method} {request.url.path} - Processing...")
    response = await call_next(request)
    process_time = (datetime.now(timezone.utc) - start_time).total_seconds()
    print(f"DEBUG: {request.method} {request.url.path} - Completed in {process_time:.4f}s with Status {response.status_code}")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all: return JSON instead of HTML for any unhandled exception."""
    import traceback
    traceback_str = traceback.format_exc()
    print(f"[GLOBAL UNHANDLED] {exc}\n{traceback_str}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )


@app.get("/api/health")
def health_check():
    redis_status = get_redis_status()
    mds = MarketDataService.get_instance()
    mds_status = mds.get_status()
    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis": redis_status,
        "market_data_service": mds_status,
    }


# Include routers
app.include_router(auth.router)
app.include_router(data.router)
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(research.router)
app.include_router(deployments.router)
app.include_router(live_trading.router)
app.include_router(cleanup_router, prefix="/api/cleanup")
app.include_router(groups_router.router)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    print(f"--- QuantLab Backend Starting on http://{host}:{port} ---")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
