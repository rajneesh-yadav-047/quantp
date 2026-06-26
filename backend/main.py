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
from backend.options_models import OptionStrategyDB, OptionLegDB  # Register option tables
from backend.routers import auth, data, strategies, backtest, research, deployments, live_trading, options
from backend.routers.options import router as options_router
from backend.routers import groups as groups_router
from backend.cleanup_api import router as cleanup_router
from backend.services.market_data_service import MarketDataService
from backend.services.redis_client import get_redis_status
from backend.services.event_bus import EventBus
from backend.services.persistence_service import PersistenceService
from backend.services.deployment_engine import DeploymentEngine

import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Initializing Database...")
    init_db()
    print("INFO: Database Initialization Complete.")
    print("INFO: Loading symbol suggestions...")
    data._load_symbol_suggestions()
    
    # Initialize new service-oriented architecture
    print("INFO: Initializing EventBus...")
    event_bus = EventBus.get_instance()
    await event_bus.start()
    print("INFO: EventBus started.")
    
    print("INFO: Initializing PersistenceService...")
    persistence = PersistenceService.get_instance()
    await persistence.start()
    print("INFO: PersistenceService started.")
    
    print("INFO: Initializing DeploymentEngine...")
    deployment_engine = DeploymentEngine.get_instance()
    await deployment_engine.initialize()
    print("INFO: DeploymentEngine initialized.")
    
    # Initialize Market Data Service if SmartAPI is configured AND connected
    print("INFO: Checking SmartAPI configuration for Market Data Service...")
    from backend.services.smartapi_manager import SmartAPIManager
    if SmartAPIManager.is_configured() and SmartAPIManager.is_connected():
        mds = MarketDataService.get_instance()
        mds.start()
        print("INFO: Market Data Service started.")
    else:
        print("INFO: SmartAPI not authenticated. Market Data Service will start on-demand after login.")
    
    yield
    
    # Shutdown
    print("INFO: Shutting down services...")
    
    mds = MarketDataService.get_instance()
    mds.stop()
    
    deployment_engine = DeploymentEngine.get_instance()
    for orch_id in list(deployment_engine.orchestrators.keys()):
        orch = deployment_engine.orchestrators.get(orch_id)
        if orch:
            orch.stop()
    
    persistence = PersistenceService.get_instance()
    await persistence.stop()
    
    event_bus = EventBus.get_instance()
    await event_bus.stop()
    
    print("INFO: All services stopped.")


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
app.include_router(options_router)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    print(f"--- QuantLab Backend Starting on http://{host}:{port} ---")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
