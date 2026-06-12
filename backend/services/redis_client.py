"""
Redis Client: Centralized Redis connection with fallback support.

Provides:
- Real Redis connection (for production)
- Fakeredis fallback (for local development without Redis server)
- Connection via REDIS_URL env variable

Usage:
    from backend.services.redis_client import get_redis, get_redis_async
    redis = get_redis()
    redis.set("key", "value")
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any

# Try real redis first, fallback to fakeredis
try:
    import redis as redis_lib
    HAS_REAL_REDIS = True
except ImportError:
    HAS_REAL_REDIS = False

try:
    import fakeredis.aioredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False


class RedisClient:
    """
    Redis client wrapper with auto-fallback to fakeredis.
    
    Environment:
        REDIS_URL: Redis connection URL (e.g., redis://localhost:6379/0)
        If not set or connection fails, uses fakeredis (in-memory).
    """
    
    _instance: Optional[Any] = None
    _pubsub_instance: Optional[Any] = None
    _is_real: bool = False
    
    @classmethod
    def _create_connection(cls) -> Any:
        redis_url = os.getenv("REDIS_URL", "")
        
        # Try real Redis first
        if redis_url and HAS_REAL_REDIS:
            try:
                client = redis_lib.from_url(redis_url, decode_responses=True)
                client.ping()
                print("[Redis] Connected to real Redis server.")
                cls._is_real = True
                return client
            except Exception as e:
                print(f"[Redis] Real Redis connection failed: {e}. Falling back to fakeredis.")
        
        # Fallback to fakeredis
        if HAS_FAKEREDIS:
            try:
                # Use synchronous fakeredis for pub/sub compatibility
                import fakeredis
                client = fakeredis.FakeRedis(decode_responses=True)
                print("[Redis] Using fakeredis (in-memory) for development.")
                cls._is_real = False
                return client
            except Exception as e:
                print(f"[Redis] Fakeredis failed: {e}")
        
        # Ultimate fallback: simple dict store
        print("[Redis] WARNING: No Redis available. Using simple dict store.")
        cls._is_real = False
        return _DictStore()
    
    @classmethod
    def get_instance(cls) -> Any:
        if cls._instance is None:
            cls._instance = cls._create_connection()
        return cls._instance
    
    @classmethod
    def is_real(cls) -> bool:
        return cls._is_real
    
    @classmethod
    def reset(cls):
        """Reset connection (useful for testing)."""
        cls._instance = None
        cls._pubsub_instance = None


class _DictStore:
    """
    Minimal dict-backed store for when Redis is completely unavailable.
    Supports basic get/set/hgetall and pubsub.
    """
    
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._hash_stores: Dict[str, Dict[str, str]] = {}
        self._subscribers: Dict[str, list] = {}
    
    def ping(self):
        return True
    
    def set(self, key: str, value: str, ex: Optional[int] = None):
        self._store[key] = value
    
    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)
    
    def delete(self, key: str):
        self._store.pop(key, None)
    
    def hset(self, name: str, key: str, value: str):
        if name not in self._hash_stores:
            self._hash_stores[name] = {}
        self._hash_stores[name][key] = value
    
    def hgetall(self, name: str) -> Dict[str, str]:
        return dict(self._hash_stores.get(name, {}))
    
    def hdel(self, name: str, key: str):
        if name in self._hash_stores:
            self._hash_stores[name].pop(key, None)
    
    def expire(self, key: str, seconds: int):
        pass
    
    def publish(self, channel: str, message: str):
        for sub in self._subscribers.get(channel, []):
            try:
                sub.put_nowait({"type": "message", "channel": channel, "data": message})
            except Exception:
                pass
    
    def pubsub(self):
        return _DictPubSub(self)


class _DictPubSub:
    def __init__(self, store: _DictStore):
        self._store = store
        self._channels: list = []
        self._queue: asyncio.Queue = asyncio.Queue()
    
    def subscribe(self, *channels):
        for ch in channels:
            self._channels.append(ch)
            if ch not in self._store._subscribers:
                self._store._subscribers[ch] = []
            self._store._subscribers[ch].append(self._queue)
    
    def unsubscribe(self, *channels):
        for ch in channels:
            if ch in self._channels:
                self._channels.remove(ch)
            if ch in self._store._subscribers:
                try:
                    self._store._subscribers[ch].remove(self._queue)
                except ValueError:
                    pass
    
    def listen(self):
        # Synchronous generator for dict store
        while True:
            if not self._queue.empty():
                yield self._queue.get_nowait()
            else:
                # Yield a heartbeat-like message to keep generator alive
                yield {"type": "heartbeat", "data": None}


def get_redis() -> Any:
    """Get the global Redis client instance."""
    return RedisClient.get_instance()


def get_redis_status() -> Dict[str, Any]:
    """Get Redis connection status."""
    return {
        "connected": RedisClient.get_instance() is not None,
        "real_redis": RedisClient.is_real(),
        "redis_url": os.getenv("REDIS_URL", "not configured (using fakeredis)"),
    }


def publish_tick(symbol: str, tick_data: Dict[str, Any]):
    """Publish a tick to the Redis pub/sub channel."""
    redis = get_redis()
    channel = f"market.tick.{symbol}"
    redis.publish(channel, json.dumps(tick_data, default=str))


def store_latest_tick(symbol: str, tick_data: Dict[str, Any]):
    """Store the latest tick in Redis hash."""
    redis = get_redis()
    key = f"market:latest_tick"
    redis.hset(key, symbol, json.dumps(tick_data, default=str))


def get_latest_tick(symbol: str) -> Optional[Dict[str, Any]]:
    """Get the latest tick from Redis."""
    redis = get_redis()
    key = f"market:latest_tick"
    data = redis.hgetall(key)
    if data and symbol in data:
        return json.loads(data[symbol])
    return None


def store_candle(symbol: str, interval: str, candle_data: Dict[str, Any]):
    """Store the latest candle in Redis."""
    redis = get_redis()
    key = f"market:candle:{interval}"
    redis.hset(key, symbol, json.dumps(candle_data, default=str))


def get_latest_candle(symbol: str, interval: str) -> Optional[Dict[str, Any]]:
    """Get the latest candle from Redis."""
    redis = get_redis()
    key = f"market:candle:{interval}"
    data = redis.hgetall(key)
    if data and symbol in data:
        return json.loads(data[symbol])
    return None


def get_all_latest_ticks() -> Dict[str, Dict[str, Any]]:
    """Get all latest ticks from Redis."""
    redis = get_redis()
    key = f"market:latest_tick"
    data = redis.hgetall(key)
    result = {}
    for symbol, tick_json in data.items():
        try:
            result[symbol] = json.loads(tick_json)
        except json.JSONDecodeError:
            pass
    return result
