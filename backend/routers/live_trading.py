"""
Live Trading Router: Mock deployment endpoints with real-time SSE streaming.

Provides:
- POST /api/live/start       — Start a mock deployment
- POST /api/live/stop/{id}   — Stop a mock deployment
- POST /api/live/pause/{id}  — Pause a mock deployment
- POST /api/live/resume/{id} — Resume a mock deployment
- GET  /api/live/status/{id} — Get deployment status + current portfolio
- GET  /api/live/trades/{id} — Get recent mock trades
- GET  /api/live/pnl/{id}    — Get recent PnL snapshots
- GET  /api/live/stream/{id} — SSE real-time event stream
- GET  /api/live/events/{id} — Get deployment event log

IMPORTANT: All endpoints are PAPER/MOCK ONLY. No real orders are placed.
"""

import json
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.database import get_db, DeploymentDB, StrategyDB, LiveTradeDB, LivePnLSnapshotDB, DeploymentEventDB
from backend.services.mock_deployment_engine import MockDeploymentEngine

router = APIRouter(prefix="/api/live", tags=["live_trading"])


class StartMockDeploymentRequest(BaseModel):
    deployment_id: str
    slippage_pct: float = 0.0
    use_real_charges: bool = True


class StartMockDeploymentResponse(BaseModel):
    status: str
    deployment_id: str
    message: str
    symbol: Optional[str] = None
    interval: Optional[str] = None
    initial_capital: Optional[float] = None


# Global engine instance
_engine: Optional[MockDeploymentEngine] = None

def get_engine() -> MockDeploymentEngine:
    global _engine
    if _engine is None:
        _engine = MockDeploymentEngine.get_instance()
    return _engine


@router.post("/start", response_model=StartMockDeploymentResponse)
async def start_mock_deployment(req: StartMockDeploymentRequest, db: Session = Depends(get_db)):
    """
    Start a mock (paper) deployment for a given deployment ID.
    
    REQUIRES SmartAPI to be authenticated first. No fallback to mock data.
    NO REAL ORDERS ARE PLACED. ALL TRADES ARE SIMULATED.
    """
    from backend.services.smartapi_manager import SmartAPIManager
    
    if not SmartAPIManager.is_connected():
        raise HTTPException(
            status_code=400,
            detail="SmartAPI not connected. Please authenticate with TOTP on the home page first."
        )
    
    engine = get_engine()
    result = await engine.start_deployment(
        deployment_id=req.deployment_id,
        db=db,
        slippage_pct=req.slippage_pct,
        use_real_charges=req.use_real_charges,
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to start deployment"))
    
    return StartMockDeploymentResponse(
        status=result["status"],
        deployment_id=result["deployment_id"],
        message=result.get("message", "Mock deployment started"),
        symbol=result.get("symbol"),
        interval=result.get("interval"),
        initial_capital=result.get("initial_capital"),
    )


@router.post("/stop/{deployment_id}")
async def stop_mock_deployment(deployment_id: str, db: Session = Depends(get_db)):
    """Stop a running mock deployment. No real orders are cancelled — there were none."""
    engine = get_engine()
    result = await engine.stop_deployment(deployment_id, db)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Deployment not found or not running")
    return result


@router.post("/pause/{deployment_id}")
async def pause_mock_deployment(deployment_id: str):
    """Pause a running mock deployment (keeps state, stops processing ticks)."""
    engine = get_engine()
    result = await engine.pause_deployment(deployment_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Deployment not found or not running")
    return result


@router.post("/resume/{deployment_id}")
async def resume_mock_deployment(deployment_id: str):
    """Resume a paused mock deployment."""
    engine = get_engine()
    result = await engine.resume_deployment(deployment_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Deployment not found or not running")
    return result


@router.get("/status/{deployment_id}")
def get_deployment_status(deployment_id: str, db: Session = Depends(get_db)):
    """Get the current status of a mock deployment, including live portfolio snapshot."""
    engine = get_engine()
    status = engine.get_runner_status(deployment_id)
    
    if not status:
        # Check if deployment exists in DB but not running
        deployment = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return {
            "deployment_id": deployment_id,
            "status": deployment.status,
            "mode": deployment.mode,
            "symbol": deployment.symbol,
            "running": False,
            "portfolio": None,
        }
    
    return {
        "deployment_id": deployment_id,
        "status": status["status"],
        "running": status["status"] in ("running", "paused"),
        "symbol": status["symbol"],
        "interval": status["interval"],
        "step": status["step"],
        "initial_capital": status["initial_capital"],
        "current_price": status["current_price"],
        "smartapi_connected": status["smartapi_connected"],
        "portfolio": status["portfolio"],
        "active_orders": status["active_orders"],
        "poll_interval": status["poll_interval"],
    }


@router.get("/trades/{deployment_id}")
def get_deployment_trades(
    deployment_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get recent mock trades for a deployment."""
    trades = db.query(LiveTradeDB).filter(
        LiveTradeDB.deployment_id == deployment_id
    ).order_by(LiveTradeDB.timestamp.desc()).limit(limit).all()
    
    return [{
        "id": t.id,
        "symbol": t.symbol,
        "direction": t.direction,
        "price": t.price,
        "qty": t.qty,
        "value": t.value,
        "brokerage": t.brokerage,
        "stt": t.stt,
        "exc_charges": t.exc_charges,
        "gst": t.gst,
        "sebi_charges": t.sebi_charges,
        "stamp_duty": t.stamp_duty,
        "total_charges": t.total_charges,
        "charges_source": t.charges_source,
        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
    } for t in trades]


@router.get("/pnl/{deployment_id}")
def get_deployment_pnl(
    deployment_id: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get recent PnL snapshots for a deployment."""
    snapshots = db.query(LivePnLSnapshotDB).filter(
        LivePnLSnapshotDB.deployment_id == deployment_id
    ).order_by(LivePnLSnapshotDB.timestamp.desc()).limit(limit).all()
    
    return [{
        "id": s.id,
        "cash": s.cash,
        "equity": s.equity,
        "unrealized_pnl": s.unrealized_pnl,
        "realized_pnl": s.realized_pnl,
        "total_fees": s.total_fees,
        "total_pnl": s.total_pnl,
        "margin_used": s.margin_used,
        "margin_free": s.margin_free,
        "position_count": s.position_count,
        "total_qty": s.total_qty,
        "positions": json.loads(s.positions_json) if s.positions_json else {},
        "timestamp": s.timestamp.isoformat() if s.timestamp else None,
    } for s in snapshots]


@router.get("/events/{deployment_id}")
def get_deployment_events(
    deployment_id: str,
    limit: int = 100,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get deployment event log (start, stop, fills, errors, etc.)."""
    query = db.query(DeploymentEventDB).filter(DeploymentEventDB.deployment_id == deployment_id)
    if event_type:
        query = query.filter(DeploymentEventDB.event_type == event_type)
    events = query.order_by(DeploymentEventDB.timestamp.desc()).limit(limit).all()
    
    return [{
        "id": e.id,
        "event_type": e.event_type,
        "message": e.message,
        "data": json.loads(e.data_json) if e.data_json else None,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
    } for e in events]


@router.get("/stream/{deployment_id}")
async def stream_deployment(deployment_id: str):
    """
    SSE stream for real-time mock deployment updates.
    
    Events:
    - tick: New candle + orders + fills + portfolio snapshot
    - fill: Individual trade fill notification
    - error: Error message
    - margin_call: Margin call liquidation event
    
    NO REAL MONEY. ALL TRADES ARE SIMULATED.
    """
    engine = get_engine()
    
    async def event_generator():
        queue = asyncio.Queue()
        
        def on_event(event_type: str, data: dict):
            try:
                queue.put_nowait({"event": event_type, "data": data})
            except Exception:
                pass
        
        engine.add_sse_callback(deployment_id, on_event)
        
        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'deployment_id': deployment_id, 'message': 'SSE stream connected. MOCK MODE — NO REAL MONEY.'})}\n\n"
            
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = message["event"]
                    data = message["data"]
                    yield f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"event: heartbeat\ndata: {json.dumps({'time': datetime.now(timezone.utc).isoformat()})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            engine.remove_sse_callback(deployment_id, on_event)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/all")
def get_all_live_deployments(db: Session = Depends(get_db)):
    """Get all deployments with their live status."""
    engine = get_engine()
    all_status = engine.get_all_status()
    
    # Also include DB deployments that aren't running
    db_deployments = db.query(DeploymentDB).all()
    running_ids = {s["deployment_id"] for s in all_status}
    
    result = []
    for s in all_status:
        result.append({
            "deployment_id": s["deployment_id"],
            "status": s["status"],
            "running": True,
            "symbol": s["symbol"],
            "interval": s["interval"],
            "portfolio": s["portfolio"],
        })
    
    for d in db_deployments:
        if d.id not in running_ids:
            result.append({
                "deployment_id": d.id,
                "status": d.status,
                "running": False,
                "symbol": d.symbol,
                "interval": None,
                "portfolio": None,
            })
    
    return result


@router.get("/market-data/status")
def get_market_data_status():
    """Get the status of the centralized Market Data Service."""
    from backend.services.market_data_service import MarketDataService
    mds = MarketDataService.get_instance()
    return mds.get_status()


@router.get("/market-data/tick/{symbol}")
def get_latest_tick(symbol: str):
    """Get the latest tick for a symbol from the Market Data Service."""
    from backend.services.redis_client import get_latest_tick
    tick = get_latest_tick(symbol)
    if not tick:
        raise HTTPException(status_code=404, detail=f"No tick data available for {symbol}")
    return tick


@router.get("/market-data/candle/{symbol}")
def get_latest_candle(symbol: str, interval: str = "5m"):
    """Get the latest candle for a symbol+interval from the Market Data Service."""
    from backend.services.redis_client import get_latest_candle
    candle = get_latest_candle(symbol, interval)
    if not candle:
        raise HTTPException(status_code=404, detail=f"No candle data available for {symbol} {interval}")
    return candle


@router.post("/market-data/subscribe/{symbol}")
def subscribe_to_symbol(symbol: str):
    """Subscribe a symbol to the Market Data Service."""
    from backend.services.market_data_service import MarketDataService, ensure_market_data_service
    import asyncio
    try:
        mds = MarketDataService.get_instance()
        if not mds._running:
            mds.start()
            asyncio.run(asyncio.sleep(2))
        mds.subscribe_symbol(symbol)
        return {"status": "subscribed", "symbol": symbol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market-data/unsubscribe/{symbol}")
def unsubscribe_from_symbol(symbol: str):
    """Unsubscribe a symbol from the Market Data Service."""
    from backend.services.market_data_service import MarketDataService
    try:
        mds = MarketDataService.get_instance()
        mds.unsubscribe_symbol(symbol)
        return {"status": "unsubscribed", "symbol": symbol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
