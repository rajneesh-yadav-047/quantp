"""
PersistenceService: Asynchronous persistence workers and queues for decoupled database writes.

Decouples the live trading loop from database I/O by:
- Enqueueing trade records, PnL snapshots, and events into async queues
- Processing queues with background worker tasks
- Batching writes where possible to reduce SQLite load
- Never blocking the main tick loop on DB operations

This service replaces the inline _save_trade(), _save_pnl_snapshot(), and _log_event()
methods that were called directly inside every tick cycle.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from backend.database import (
    LiveTradeDB, LivePnLSnapshotDB, DeploymentEventDB,
    SessionLocal
)


@dataclass
class PersistenceJob:
    """A single job to be persisted."""
    job_type: str  # "trade", "pnl_snapshot", "event"
    deployment_id: str
    strategy_id: str
    payload: Dict[str, Any]
    priority: int = 0  # Higher = processed sooner
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AsyncPersistenceWorker:
    """
    Background worker that drains the persistence queue and writes to the database.
    
    Configurable batch size and flush interval for efficiency.
    """
    
    def __init__(
        self,
        queue: asyncio.Queue,
        batch_size: int = 10,
        flush_interval_seconds: float = 2.0,
    ):
        self.queue = queue
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._pending: List[PersistenceJob] = []
    
    async def start(self):
        """Start the background worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
    
    async def stop(self):
        """Stop the worker, flushing any pending jobs."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Flush remaining
        if self._pending:
            await self._flush_batch(self._pending)
            self._pending = []
    
    async def _worker_loop(self):
        """Main worker loop: batch jobs and flush periodically."""
        while self._running:
            try:
                # Wait for a job or timeout
                job = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=self.flush_interval_seconds
                )
                self._pending.append(job)
                
                # Drain up to batch_size immediately available
                for _ in range(self.batch_size - 1):
                    try:
                        job = self.queue.get_nowait()
                        self._pending.append(job)
                    except asyncio.QueueEmpty:
                        break
                
                # Flush if batch is full
                if len(self._pending) >= self.batch_size:
                    await self._flush_batch(self._pending)
                    self._pending = []
                    
            except asyncio.TimeoutError:
                # Flush any pending jobs on timeout
                if self._pending:
                    await self._flush_batch(self._pending)
                    self._pending = []
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[PersistenceWorker] Worker loop error: {e}")
    
    async def _flush_batch(self, jobs: List[PersistenceJob]):
        """Persist a batch of jobs to the database."""
        if not jobs:
            return
        
        # Group by job type for efficient bulk inserts
        trades = []
        snapshots = []
        events = []
        
        for job in jobs:
            if job.job_type == "trade":
                trades.append(job)
            elif job.job_type == "pnl_snapshot":
                snapshots.append(job)
            elif job.job_type == "event":
                events.append(job)
        
        # Use synchronous DB calls in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,  # default executor
            self._sync_flush,
            trades, snapshots, events
        )
    
    def _sync_flush(self, trades: List[PersistenceJob], snapshots: List[PersistenceJob], events: List[PersistenceJob]):
        """Synchronous database flush (runs in thread pool)."""
        db = SessionLocal()
        try:
            # Flush trades
            for job in trades:
                p = job.payload
                live_trade = LiveTradeDB(
                    id=str(uuid.uuid4()),
                    deployment_id=job.deployment_id,
                    strategy_id=job.strategy_id,
                    symbol=p.get("symbol", ""),
                    direction=p.get("direction", ""),
                    price=p.get("price", 0.0),
                    qty=p.get("qty", 0),
                    value=p.get("value", 0.0),
                    brokerage=p.get("brokerage", 0.0),
                    stt=p.get("stt", 0.0),
                    exc_charges=p.get("exc_charges", 0.0),
                    gst=p.get("gst", 0.0),
                    sebi_charges=p.get("sebi_charges", 0.0),
                    stamp_duty=p.get("stamp_duty", 0.0),
                    total_charges=p.get("total_charges", 0.0),
                    charges_source=p.get("charges_source", "calculated"),
                )
                db.add(live_trade)
            
            # Flush PnL snapshots
            for job in snapshots:
                p = job.payload
                snapshot = LivePnLSnapshotDB(
                    id=str(uuid.uuid4()),
                    deployment_id=job.deployment_id,
                    strategy_id=job.strategy_id,
                    cash=p.get("cash", 0.0),
                    equity=p.get("equity", 0.0),
                    unrealized_pnl=p.get("unrealized_pnl", 0.0),
                    realized_pnl=p.get("realized_pnl", 0.0),
                    total_fees=p.get("total_fees", 0.0),
                    total_pnl=p.get("total_pnl", 0.0),
                    margin_used=p.get("margin_used", 0.0),
                    margin_free=p.get("margin_free", 0.0),
                    position_count=p.get("position_count", 0),
                    total_qty=p.get("total_qty", 0),
                    positions_json=json.dumps(p.get("positions", {})),
                )
                db.add(snapshot)
            
            # Flush events
            for job in events:
                p = job.payload
                event = DeploymentEventDB(
                    id=str(uuid.uuid4()),
                    deployment_id=job.deployment_id,
                    event_type=p.get("event_type", ""),
                    message=p.get("message", ""),
                    data_json=json.dumps(p.get("data")) if p.get("data") else None,
                )
                db.add(event)
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[PersistenceWorker] DB flush error: {e}")
        finally:
            db.close()


class PersistenceService:
    """
    Centralized persistence service with async queues and background workers.
    
    Usage:
        service = PersistenceService.get_instance()
        await service.start()
        service.enqueue_trade(deployment_id, strategy_id, {...})
        service.enqueue_pnl_snapshot(deployment_id, strategy_id, {...})
        service.enqueue_event(deployment_id, "fill", "BUY 100 SBIN", {...})
    """
    
    _instance: Optional['PersistenceService'] = None
    
    def __init__(
        self,
        batch_size: int = 10,
        flush_interval_seconds: float = 2.0,
        max_queue_size: int = 1000,
    ):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.worker = AsyncPersistenceWorker(
            queue=self.queue,
            batch_size=batch_size,
            flush_interval_seconds=flush_interval_seconds,
        )
    
    @classmethod
    def get_instance(cls) -> 'PersistenceService':
        if cls._instance is None:
            cls._instance = PersistenceService()
        return cls._instance
    
    async def start(self):
        """Start the persistence service."""
        await self.worker.start()
    
    async def stop(self):
        """Stop the persistence service, flushing all pending jobs."""
        await self.worker.stop()
    
    def enqueue_trade(self, deployment_id: str, strategy_id: str, trade_data: Dict[str, Any]):
        """Enqueue a trade for async persistence."""
        job = PersistenceJob(
            job_type="trade",
            deployment_id=deployment_id,
            strategy_id=strategy_id,
            payload=trade_data,
            priority=1,  # Trades are high priority
        )
        try:
            self.queue.put_nowait(job)
        except asyncio.QueueFull:
            print(f"[PersistenceService] Trade queue full, dropping trade: {trade_data.get('symbol', 'unknown')}")
    
    def enqueue_pnl_snapshot(self, deployment_id: str, strategy_id: str, snapshot_data: Dict[str, Any]):
        """Enqueue a PnL snapshot for async persistence."""
        job = PersistenceJob(
            job_type="pnl_snapshot",
            deployment_id=deployment_id,
            strategy_id=strategy_id,
            payload=snapshot_data,
            priority=0,
        )
        try:
            self.queue.put_nowait(job)
        except asyncio.QueueFull:
            print(f"[PersistenceService] Snapshot queue full, dropping snapshot for {deployment_id}")
    
    def enqueue_event(self, deployment_id: str, event_type: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Enqueue a deployment event for async persistence."""
        job = PersistenceJob(
            job_type="event",
            deployment_id=deployment_id,
            strategy_id="",  # events are deployment-level
            payload={
                "event_type": event_type,
                "message": message,
                "data": data,
            },
            priority=2,  # Events are highest priority
        )
        try:
            self.queue.put_nowait(job)
        except asyncio.QueueFull:
            print(f"[PersistenceService] Event queue full, dropping event: {event_type}")
    
    async def flush(self):
        """Force flush all pending jobs immediately."""
        await self.worker.stop()
        self.worker = AsyncPersistenceWorker(
            queue=self.queue,
            batch_size=self.worker.batch_size,
            flush_interval_seconds=self.worker.flush_interval_seconds,
        )
        await self.worker.start()


async def ensure_persistence_service() -> PersistenceService:
    """Ensure the persistence service is started and return it."""
    service = PersistenceService.get_instance()
    await service.start()
    return service
