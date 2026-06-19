"""
SharedCacheService: Shared cache for historical candle storage across all deployments.

Improves memory efficiency when running multiple strategies simultaneously by maintaining
a single shared cache of historical candles rather than per-deployment copies.

Features:
- Per-symbol, per-interval sliding window of candles (configurable max size)
- Thread-safe / async-safe access
- Redis-backed for cross-process sharing, with in-memory fallback
- All deployments read from the same cache, no duplication
"""

import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from datetime import datetime, timezone

from backend.services.redis_client import get_redis


class SharedCacheService:
    """
    Shared cache service for historical market data.
    
    Maintains a centralized candle history so multiple deployments
    watching the same symbol+interval share memory.
    """
    
    _instance: Optional['SharedCacheService'] = None
    
    # Default max candles per symbol+interval
    DEFAULT_MAX_CANDLES = 2000
    
    def __init__(self, max_candles: int = DEFAULT_MAX_CANDLES):
        self._max_candles = max_candles
        # In-memory cache: {symbol: {interval: deque of candles}}
        self._cache: Dict[str, Dict[str, deque]] = {}
        self._lock = asyncio.Lock()
        self._redis_prefix = "shared_cache:candles"
    
    @classmethod
    def get_instance(cls, max_candles: int = DEFAULT_MAX_CANDLES) -> 'SharedCacheService':
        if cls._instance is None:
            cls._instance = cls(max_candles=max_candles)
        return cls._instance
    
    def _make_key(self, symbol: str, interval: str) -> str:
        return f"{symbol}:{interval}"
    
    def _make_redis_key(self, symbol: str, interval: str) -> str:
        return f"{self._redis_prefix}:{symbol}:{interval}"
    
    async def append_candle(self, symbol: str, interval: str, candle: Dict[str, Any]):
        """Append a candle to the shared cache for a symbol+interval."""
        key = self._make_key(symbol, interval)
        
        async with self._lock:
            if symbol not in self._cache:
                self._cache[symbol] = {}
            if interval not in self._cache[symbol]:
                self._cache[symbol][interval] = deque(maxlen=self._max_candles)
            
            self._cache[symbol][interval].append(candle)
        
        # Also store latest in Redis for cross-process access
        try:
            redis = get_redis()
            redis_key = self._make_redis_key(symbol, interval)
            # Store as JSON list (truncated to max)
            async with self._lock:
                candles_list = list(self._cache[symbol][interval])
            redis.set(redis_key, json.dumps(candles_list, default=str))
        except Exception:
            pass
    
    async def get_candles(self, symbol: str, interval: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent candles for a symbol+interval."""
        key = self._make_key(symbol, interval)
        
        async with self._lock:
            if symbol in self._cache and interval in self._cache[symbol]:
                candles = list(self._cache[symbol][interval])
                if count:
                    return candles[-count:]
                return candles
        
        # Try Redis fallback
        try:
            redis = get_redis()
            redis_key = self._make_redis_key(symbol, interval)
            data = redis.get(redis_key)
            if data:
                candles = json.loads(data)
                if count:
                    return candles[-count:]
                return candles
        except Exception:
            pass
        
        return []
    
    async def get_latest_candle(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Get the most recent candle for a symbol+interval."""
        candles = await self.get_candles(symbol, interval, count=1)
        return candles[0] if candles else None
    
    async def get_candles_as_df_rows(self, symbol: str, interval: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get candles formatted as DataFrame-compatible rows."""
        return await self.get_candles(symbol, interval, count)
    
    async def clear_symbol(self, symbol: str):
        """Clear all cached data for a symbol."""
        async with self._lock:
            if symbol in self._cache:
                del self._cache[symbol]
        
        try:
            redis = get_redis()
            # Find and delete all keys for this symbol
            pattern = f"{self._redis_prefix}:{symbol}:*"
            # Simple approach: try common intervals
            for interval in ["1m", "5m", "15m", "1h", "1d"]:
                redis.delete(f"{self._redis_prefix}:{symbol}:{interval}")
        except Exception:
            pass
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        stats = {
            "symbols": list(self._cache.keys()),
            "total_symbol_intervals": 0,
            "max_candles_per_window": self._max_candles,
        }
        for sym, intervals in self._cache.items():
            stats["total_symbol_intervals"] += len(intervals)
        return stats
    
    async def warm_cache(self, symbol: str, interval: str, candles: List[Dict[str, Any]]):
        """Pre-load candles into the cache (e.g., from historical data)."""
        async with self._lock:
            if symbol not in self._cache:
                self._cache[symbol] = {}
            if interval not in self._cache[symbol]:
                self._cache[symbol][interval] = deque(maxlen=self._max_candles)
            
            # Extend existing candles, maintaining window
            existing = self._cache[symbol][interval]
            for c in candles:
                existing.append(c)
        
        # Sync to Redis
        try:
            redis = get_redis()
            redis_key = self._make_redis_key(symbol, interval)
            async with self._lock:
                candles_list = list(self._cache[symbol][interval])
            redis.set(redis_key, json.dumps(candles_list, default=str))
        except Exception:
            pass


def get_shared_cache() -> SharedCacheService:
    """Get the global shared cache service instance."""
    return SharedCacheService.get_instance()
