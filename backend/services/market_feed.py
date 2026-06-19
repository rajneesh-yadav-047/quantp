"""
MarketFeed: Dedicated Market Feed abstraction layer.

Provides a unified interface for retrieving live ticks and candles without any trading logic.

Responsibilities:
- Abstract SmartAPI/WebSocket/Redis/candle aggregation details
- Expose clean APIs: get_latest_tick(), get_latest_candle(), get_candles()
- Subscribe/unsubscribe symbols for market data streaming
- Normalize symbol formats across all data sources

No trading logic. No order management. No portfolio concerns.
"""

import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone

from backend.services.redis_client import get_latest_tick, get_latest_candle
from backend.services.market_data_service import MarketDataService, ensure_market_data_service
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.data_service import normalize_symbol


class MarketFeed:
    """
    Unified market data feed abstraction.
    
    Encapsulates all SmartAPI, WebSocket, Redis, and candle aggregation
    functionality behind a single, clean interface.
    """
    
    def __init__(self):
        self._mds: Optional[MarketDataService] = None
        self._subscribed_symbols: set = set()
        self._callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
    
    async def initialize(self, symbols: Optional[List[str]] = None) -> 'MarketFeed':
        """Initialize the market feed and ensure MDS is running."""
        if symbols:
            self._mds = await ensure_market_data_service(symbols)
            for sym in symbols:
                self._subscribed_symbols.add(sym)
        else:
            self._mds = MarketDataService.get_instance()
            if not self._mds._running:
                self._mds.start()
                await asyncio.sleep(2)
        return self
    
    def subscribe_symbol(self, symbol: str) -> bool:
        """Subscribe to a symbol for real-time data."""
        if self._mds is None:
            return False
        self._subscribed_symbols.add(symbol)
        return self._mds.subscribe_symbol(symbol)
    
    def unsubscribe_symbol(self, symbol: str) -> bool:
        """Unsubscribe from a symbol."""
        self._subscribed_symbols.discard(symbol)
        if self._mds:
            return self._mds.unsubscribe_symbol(symbol)
        return True
    
    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest tick for a symbol from Redis ONLY."""
        return get_latest_tick(symbol)
    
    def get_latest_candle(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Get the latest candle for a symbol+interval from Redis ONLY."""
        return get_latest_candle(symbol, interval)
    
    def get_candles(self, symbol: str, interval: str, count: int = 1) -> List[Dict[str, Any]]:
        """
        Get recent candles for a symbol+interval.
        Currently returns at most the latest candle from Redis.
        For full historical series, use SharedCacheService.
        """
        candle = self.get_latest_candle(symbol, interval)
        if candle:
            return [candle]
        return []
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """Get the Last Traded Price for a symbol."""
        tick = self.get_latest_tick(symbol)
        if tick and tick.get("ltp", 0) > 0:
            return float(tick["ltp"])
        return None
    
    def get_market_status(self) -> Dict[str, Any]:
        """Get current market data feed status."""
        if self._mds:
            return self._mds.get_status()
        return {"status": "not_initialized", "running": False}
    
    def add_tick_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Register a callback for real-time tick events."""
        self._callbacks.append(callback)
        if self._mds:
            self._mds.add_callback(callback)
    
    def remove_tick_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Remove a tick callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
        if self._mds:
            self._mds.remove_callback(callback)
    
    def normalize_symbol(self, symbol: str, interval: str = "FIVE_MINUTE") -> str:
        """Normalize a symbol to canonical format using SmartAPI if available."""
        client = SmartAPIManager.get_client() if SmartAPIManager.is_connected() else None
        if client:
            return normalize_symbol(symbol, interval, client)
        return symbol
    
    @property
    def is_connected(self) -> bool:
        """Check if the underlying market data service is connected."""
        if self._mds:
            return self._mds._status == "connected"
        return False
    
    @property
    def subscribed_symbols(self) -> List[str]:
        """List of currently subscribed symbols."""
        return list(self._subscribed_symbols)


async def create_market_feed(symbols: Optional[List[str]] = None) -> MarketFeed:
    """Factory function to create and initialize a MarketFeed instance."""
    feed = MarketFeed()
    await feed.initialize(symbols)
    return feed
