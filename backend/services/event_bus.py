"""
EventBus: Centralized event-driven communication layer for the live trading system.

Provides decoupled pub/sub for:
- Market data updates (ticks, candles)
- Trade execution events
- Portfolio state changes
- Strategy logs
- Deployment lifecycle events (start, stop, pause, resume, error)
- Frontend SSE notifications

Components publish events to the EventBus without knowing who consumes them.
Consumers subscribe to event types and receive callbacks asynchronously.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict


@dataclass
class Event:
    """Standardized event envelope."""
    event_type: str
    source: str  # component that published the event
    deployment_id: Optional[str]  # None for global events
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "source": self.source,
            "deployment_id": self.deployment_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventBus:
    """
    Centralized event bus for decoupled component communication.
    
    Singleton: one bus per application.
    """
    
    _instance: Optional['EventBus'] = None
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._deployment_subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._global_subscribers: List[Callable[[Event], None]] = []
        self._lock = asyncio.Lock()
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._dispatch_task: Optional[asyncio.Task] = None
        self._running = False
    
    @classmethod
    def get_instance(cls) -> 'EventBus':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def start(self):
        """Start the background event dispatch task."""
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
    
    async def stop(self):
        """Stop the event bus."""
        self._running = False
        if self._dispatch_task and not self._dispatch_task.done():
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
    
    async def _dispatch_loop(self):
        """Background loop that dispatches queued events to subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[EventBus] Dispatch error: {e}")
    
    async def _dispatch_event(self, event: Event):
        """Dispatch a single event to all matching subscribers."""
        # Global subscribers get everything
        for cb in self._global_subscribers:
            try:
                cb(event)
            except Exception as e:
                print(f"[EventBus] Global subscriber error: {e}")
        
        # Event-type subscribers
        type_key = event.event_type
        for cb in self._subscribers.get(type_key, []):
            try:
                cb(event)
            except Exception as e:
                print(f"[EventBus] Type subscriber error ({type_key}): {e}")
        
        # Deployment-specific subscribers
        if event.deployment_id:
            for cb in self._deployment_subscribers.get(event.deployment_id, []):
                try:
                    cb(event)
                except Exception as e:
                    print(f"[EventBus] Deployment subscriber error ({event.deployment_id}): {e}")
    
    def publish(self, event: Event):
        """Publish an event to the bus (non-blocking, queues for dispatch)."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            print(f"[EventBus] Event queue full, dropping event: {event.event_type}")
    
    def publish_sync(self, event_type: str, source: str, deployment_id: Optional[str], payload: Dict[str, Any]):
        """Convenience method to publish an event synchronously."""
        event = Event(
            event_type=event_type,
            source=source,
            deployment_id=deployment_id,
            payload=payload,
        )
        self.publish(event)
    
    def subscribe(self, event_type: str, callback: Callable[[Event], None]):
        """Subscribe to a specific event type."""
        self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]):
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass
    
    def subscribe_deployment(self, deployment_id: str, callback: Callable[[Event], None]):
        """Subscribe to all events for a specific deployment."""
        self._deployment_subscribers[deployment_id].append(callback)
    
    def unsubscribe_deployment(self, deployment_id: str, callback: Callable[[Event], None]):
        """Unsubscribe from a deployment's events."""
        if deployment_id in self._deployment_subscribers:
            try:
                self._deployment_subscribers[deployment_id].remove(callback)
            except ValueError:
                pass
    
    def subscribe_global(self, callback: Callable[[Event], None]):
        """Subscribe to ALL events globally."""
        self._global_subscribers.append(callback)
    
    def unsubscribe_global(self, callback: Callable[[Event], None]):
        """Unsubscribe from global events."""
        try:
            self._global_subscribers.remove(callback)
        except ValueError:
            pass


# Convenience event type constants
class EventType:
    MARKET_TICK = "market_tick"
    MARKET_CANDLE = "tick"       # Frontend expects "tick" for candle updates
    TRADE_FILL = "fill"          # Frontend expects "fill" for trade fills
    ORDER_SUBMITTED = "order_submitted"
    PORTFOLIO_UPDATE = "portfolio_update"
    MARGIN_CALL = "margin_call"
    STRATEGY_LOG = "strategy_log"
    DEPLOYMENT_START = "start"   # Frontend expects "start"
    DEPLOYMENT_STOP = "stop"     # Frontend expects "stop"
    DEPLOYMENT_PAUSE = "pause"   # Frontend expects "pause"
    DEPLOYMENT_RESUME = "resume" # Frontend expects "resume"
    DEPLOYMENT_ERROR = "error"   # Frontend expects "error"
    PNL_SNAPSHOT = "pnl_snapshot"
    HEARTBEAT = "heartbeat"
    MANUAL_ORDER = "manual_order"


async def ensure_event_bus() -> EventBus:
    """Ensure the event bus is started and return it."""
    bus = EventBus.get_instance()
    if not bus._running:
        await bus.start()
    return bus
