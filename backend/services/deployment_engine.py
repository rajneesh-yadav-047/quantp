"""
DeploymentEngine: Central manager for all active deployment orchestrators.

Replaces the monolithic MockDeploymentEngine with a service-oriented manager that
coordinates multiple lightweight DeploymentOrchestrator instances.

Responsibilities:
- Start/stop/pause/resume individual deployments
- Manage orchestrator lifecycle (create, track, destroy)
- Route SSE callbacks through EventBus
- Provide aggregate status queries

Each deployment gets its own orchestrator with its own dedicated services.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session

from backend.services.deployment_orchestrator import DeploymentOrchestrator
from backend.services.event_bus import EventBus, Event, EventType, ensure_event_bus
from backend.database import DeploymentDB, StrategyDB


class DeploymentEngine:
    """
    Central engine managing all active deployment orchestrators.
    
    Singleton: one engine per application.
    """
    
    _instance: Optional['DeploymentEngine'] = None
    
    def __init__(self):
        self.orchestrators: Dict[str, DeploymentOrchestrator] = {}
        self._lock = asyncio.Lock()
        self._event_bus: Optional[EventBus] = None
        self._sse_registry: Dict[str, Dict[int, Callable]] = {}  # deployment_id -> {id(wrapper): wrapper}
    
    @classmethod
    def get_instance(cls) -> 'DeploymentEngine':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self):
        """Initialize the engine and ensure EventBus is started."""
        self._event_bus = await ensure_event_bus()
    
    async def start_deployment(
        self,
        deployment_id: str,
        db: Session,
        slippage_pct: float = 0.0,
        use_real_charges: bool = True,
        pnl_snapshot_interval_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """Start a deployment orchestrator for a given deployment ID."""
        async with self._lock:
            if deployment_id in self.orchestrators and self.orchestrators[deployment_id].status not in ("stopped",):
                return {"status": "already_running", "deployment_id": deployment_id}
            
            # Load deployment and strategy
            deployment = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
            if not deployment:
                return {"status": "error", "message": "Deployment not found"}
            
            strategy = db.query(StrategyDB).filter(StrategyDB.id == deployment.strategy_id).first()
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
            
            # Determine symbol and interval
            import json
            symbols = json.loads(strategy.symbols) if strategy.symbols else ["NSE:SBIN-EQ"]
            symbol = deployment.symbol or symbols[0]
            interval = strategy.interval or "FIVE_MINUTE"
            initial_capital = strategy.initial_capital or 100000.0
            max_position_size = strategy.max_position_size
            
            # Update deployment status
            deployment.status = "active"
            db.commit()
            
            # Create orchestrator
            orchestrator = DeploymentOrchestrator(
                deployment_id=deployment_id,
                strategy=strategy,
                symbol=symbol,
                interval=interval,
                initial_capital=initial_capital,
                max_position_size=max_position_size,
                slippage_pct=slippage_pct,
                trade_type="INTRADAY",
                use_real_charges=use_real_charges,
                pnl_snapshot_interval_seconds=pnl_snapshot_interval_seconds,
            )
            
            self.orchestrators[deployment_id] = orchestrator
            await orchestrator.start()
            
            return {
                "status": "started",
                "deployment_id": deployment_id,
                "symbol": symbol,
                "interval": interval,
                "initial_capital": initial_capital,
                "message": "MOCK DEPLOYMENT STARTED — NO REAL MONEY IS BEING USED. All trades are simulated.",
            }
    
    async def stop_deployment(self, deployment_id: str, db: Session) -> Dict[str, Any]:
        """Stop a running deployment."""
        async with self._lock:
            orchestrator = self.orchestrators.get(deployment_id)
            if not orchestrator:
                return {"status": "not_found", "deployment_id": deployment_id}
            
            orchestrator.stop()
            
            # Update deployment status
            deployment = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
            if deployment:
                deployment.status = "stopped"
                db.commit()
            
            del self.orchestrators[deployment_id]
            
            return {
                "status": "stopped",
                "deployment_id": deployment_id,
                "message": "Mock deployment stopped. No real orders were placed.",
            }
    
    async def pause_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Pause a running deployment."""
        async with self._lock:
            orchestrator = self.orchestrators.get(deployment_id)
            if not orchestrator:
                return {"status": "not_found"}
            orchestrator.pause()
            return {"status": "paused", "deployment_id": deployment_id}
    
    async def resume_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Resume a paused deployment."""
        async with self._lock:
            orchestrator = self.orchestrators.get(deployment_id)
            if not orchestrator:
                return {"status": "not_found"}
            orchestrator.resume()
            return {"status": "resumed", "deployment_id": deployment_id}
    
    def get_orchestrator_status(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific orchestrator."""
        orchestrator = self.orchestrators.get(deployment_id)
        if not orchestrator:
            return None
        return orchestrator.get_status()
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status for all active orchestrators."""
        return [orch.get_status() for orch in self.orchestrators.values()]
    
    def add_sse_callback(self, deployment_id: str, callback: Callable[[str, Dict[str, Any]], None]):
        """Add an SSE callback for a deployment via EventBus."""
        if not self._event_bus:
            return
        
        def event_wrapper(event: Event):
            if event.deployment_id == deployment_id:
                callback(event.event_type, event.payload)
        
        # Register the wrapper so we can remove it later
        if deployment_id not in self._sse_registry:
            self._sse_registry[deployment_id] = {}
        wrapper_id = id(event_wrapper)
        self._sse_registry[deployment_id][wrapper_id] = event_wrapper
        
        # Subscribe to all event types for this deployment
        self._event_bus.subscribe_deployment(deployment_id, event_wrapper)
    
    def remove_sse_callback(self, deployment_id: str, callback: Callable[[str, Dict[str, Any]], None]):
        """Remove an SSE callback for a deployment."""
        if not self._event_bus or deployment_id not in self._sse_registry:
            return
        
        # Unsubscribe all wrappers for this deployment (best-effort cleanup)
        for wrapper_id, wrapper in list(self._sse_registry[deployment_id].items()):
            self._event_bus.unsubscribe_deployment(deployment_id, wrapper)
        
        self._sse_registry[deployment_id].clear()
    
    def get_orchestrator(self, deployment_id: str) -> Optional[DeploymentOrchestrator]:
        """Get a raw orchestrator instance (for manual order placement, etc.)."""
        return self.orchestrators.get(deployment_id)


# Backwards-compatible global instance accessor
_old_engine: Optional[Any] = None

def get_deployment_engine() -> DeploymentEngine:
    """Get the global DeploymentEngine instance."""
    return DeploymentEngine.get_instance()


async def ensure_deployment_engine() -> DeploymentEngine:
    """Ensure the deployment engine is initialized."""
    engine = DeploymentEngine.get_instance()
    await engine.initialize()
    return engine
