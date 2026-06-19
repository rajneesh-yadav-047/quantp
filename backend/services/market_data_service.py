"""
Market Data Service: Centralized real-time tick streaming via SmartWebSocketV2.

Architecture:
    SmartWebSocketV2 (Angel One)
           ↓
    Tick Parser (QUOTE mode) — handles actual SmartWebSocketV2 format
           ↓
    Redis Pub/Sub (market.tick.{symbol})
           ↓
    Redis Hash (market:latest_tick)
           ↓
    Candle Aggregator (1m, 5m, 15m) — thread-safe, no asyncio
           ↓
    Redis Hash (market:candle.{interval})

Usage:
    from backend.services.market_data_service import MarketDataService
    mds = MarketDataService.get_instance()
    mds.start()
    mds.subscribe_symbol("NSE:SBIN-EQ")
"""

import os
import json
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field

from backend.services.redis_client import (
    get_redis, publish_tick, store_latest_tick, store_candle,
    get_latest_tick, get_latest_candle
)
from backend.services.smartapi_manager import SmartAPIManager
from backend.smartapi import SmartAPIClient

# SmartAPI WebSocket V2 import
try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    HAS_SMARTWS = True
except ImportError as e:
    print(f"[MarketDataService] SmartWebSocketV2 not available: {e}")
    SmartWebSocketV2 = None
    HAS_SMARTWS = False


@dataclass
class CandleState:
    """In-memory candle state for a symbol+interval."""
    symbol: str
    interval: str  # "1m", "5m", "15m", "1h", "1d"
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    volume: int = 0
    open_interest: int = 0
    start_time: Optional[datetime] = None
    
    def is_new_candle(self, tick_time: datetime, interval: str) -> bool:
        """Check if tick belongs to a new candle interval."""
        if self.start_time is None:
            return True
        interval_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 375  # 375 = 9:15-15:30
        }.get(interval, 1)
        return tick_time >= self.start_time + timedelta(minutes=interval_minutes)
    
    def reset(self, tick_time: datetime, ltp: float, volume: int = 0, oi: int = 0):
        """Start a new candle."""
        self.start_time = tick_time
        self.open_price = ltp
        self.high_price = ltp
        self.low_price = ltp
        self.close_price = ltp
        self.volume = volume
        self.open_interest = oi
    
    def update(self, ltp: float, volume: int = 0, oi: int = 0):
        """Update candle with new tick."""
        self.high_price = max(self.high_price, ltp)
        self.low_price = min(self.low_price, ltp)
        self.close_price = ltp
        self.volume += volume
        if oi:
            self.open_interest = oi
    
    def to_dict(self, tick_time: datetime) -> Dict[str, Any]:
        return {
            "time": tick_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": round(self.open_price, 2),
            "high": round(self.high_price, 2),
            "low": round(self.low_price, 2),
            "close": round(self.close_price, 2),
            "volume": self.volume,
            "open_interest": self.open_interest,
        }


class CandleAggregator:
    """
    Aggregates raw ticks into candles for multiple intervals.
    Maintains in-memory state and publishes completed candles to Redis.
    
    SYNCHRONOUS — safe to call from WebSocket daemon thread.
    """
    
    INTERVALS = ["1m", "5m", "15m", "1h", "1d"]
    
    def __init__(self):
        self._candles: Dict[str, Dict[str, CandleState]] = {}
        self._lock = threading.Lock()
    
    def _key(self, symbol: str, interval: str) -> str:
        return f"{symbol}:{interval}"
    
    def process_tick(self, symbol: str, tick_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Process a tick and update all interval candles.
        Returns dict of completed candles (if any interval finalized).
        """
        ltp = tick_data.get("ltp", 0)
        volume = tick_data.get("volume", 0)
        oi = tick_data.get("oi", 0)
        timestamp_str = tick_data.get("timestamp", tick_data.get("exchange_timestamp", ""))
        
        try:
            tick_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            tick_time = datetime.now(timezone.utc)
        
        completed_candles = {}
        
        with self._lock:
            if symbol not in self._candles:
                self._candles[symbol] = {}
            
            for interval in self.INTERVALS:
                key = self._key(symbol, interval)
                if key not in self._candles[symbol]:
                    self._candles[symbol][key] = CandleState(symbol, interval)
                
                candle = self._candles[symbol][key]
                
                if candle.is_new_candle(tick_time, interval):
                    # Finalize previous candle
                    if candle.start_time is not None:
                        completed_candles[interval] = candle.to_dict(
                            candle.start_time
                        )
                    # Start new candle
                    candle.reset(tick_time, ltp, volume, oi)
                else:
                    candle.update(ltp, volume, oi)
        
        return completed_candles
    
    def get_current_candle(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Get the current forming candle for a symbol+interval."""
        key = self._key(symbol, interval)
        if symbol in self._candles and key in self._candles[symbol]:
            candle = self._candles[symbol][key]
            if candle.start_time:
                return candle.to_dict(candle.start_time)
        return None
    
    def reset_symbol(self, symbol: str):
        """Reset all candles for a symbol."""
        if symbol in self._candles:
            del self._candles[symbol]


class MarketDataService:
    """
    Centralized market data service.
    
    Maintains ONE SmartWebSocketV2 connection and broadcasts
    ticks to all subscribers via Redis Pub/Sub.
    
    Singleton pattern: only one instance in the app.
    """
    
    _instance: Optional['MarketDataService'] = None
    _lock = asyncio.Lock()
    
    # Exchange type mapping for SmartWebSocketV2
    EXCHANGE_TYPES = {
        "NSE": 1,
        "NFO": 2,
        "BSE": 3,
        "MCX": 4,
        "NCDEX": 5,
    }
    
    # Reverse mapping: exchange_type -> exchange name
    EXCHANGE_NAMES = {1: "NSE", 2: "NFO", 3: "BSE", 4: "MCX", 5: "NCDEX"}
    
    def __init__(self):
        self._ws: Optional[SmartWebSocketV2] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
        self._subscribed_symbols: Set[str] = set()
        self._aggregator = CandleAggregator()
        self._callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._smartapi_client: Optional[Any] = None
        self._status = "idle"  # idle, connecting, connected, error
        self._last_tick_time: Optional[datetime] = None
        self._total_ticks = 0
        # Token -> symbol cache for fast WebSocket tick resolution
        self._token_to_symbol: Dict[str, str] = {}
        
    @classmethod
    def get_instance(cls) -> 'MarketDataService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _resolve_token(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Resolve symbol to token info using SmartAPI client."""
        client = SmartAPIManager.get_client()
        if not client:
            return None
        return client.resolve_symbol(symbol)
    
    def _resolve_token_to_symbol(self, token: str, exchange_type: int = 1) -> Optional[str]:
        """Resolve a token ID to a normalized symbol like NSE:SBIN-EQ."""
        # Check cache first
        if token in self._token_to_symbol:
            return self._token_to_symbol[token]
        
        # Try SmartAPIClient token lookup
        client = SmartAPIManager.get_client()
        if client:
            token_info = SmartAPIClient.get_token_info(token)
            if token_info:
                symbol = token_info.get("symbol", "")
                exch = token_info.get("exch_seg", self.EXCHANGE_NAMES.get(exchange_type, "NSE"))
                if symbol:
                    normalized = f"{exch}:{symbol}"
                    self._token_to_symbol[token] = normalized
                    return normalized
        
        # Fallback: try to build from known subscription mappings
        exchange_name = self.EXCHANGE_NAMES.get(exchange_type, "NSE")
        
        # Try matching against our subscribed symbols
        for sub_sym in self._subscribed_symbols:
            token_info = self._resolve_token(sub_sym)
            if token_info and str(token_info.get("token", "")) == str(token):
                self._token_to_symbol[token] = sub_sym
                return sub_sym
        
        return None
    
    def _build_subscription_list(self) -> List[Dict[str, Any]]:
        """Build token list for WebSocket subscription."""
        token_list = []
        exchange_groups: Dict[int, List[str]] = {}
        
        for symbol in self._subscribed_symbols:
            token_info = self._resolve_token(symbol)
            if not token_info:
                print(f"[MarketDataService] Could not resolve token for {symbol}")
                continue
            
            exchange = token_info.get("exch_seg", "NSE")
            exchange_type = self.EXCHANGE_TYPES.get(exchange, 1)
            token = token_info.get("token", "")
            
            # Pre-populate token cache
            self._token_to_symbol[str(token)] = symbol
            
            if exchange_type not in exchange_groups:
                exchange_groups[exchange_type] = []
            exchange_groups[exchange_type].append(token)
        
        for exchange_type, tokens in exchange_groups.items():
            token_list.append({
                "exchangeType": exchange_type,
                "tokens": tokens
            })
        
        return token_list
    
    def _on_data(self, wsapp, message: Dict[str, Any]):
        """Handle incoming WebSocket tick data."""
        try:
            self._total_ticks += 1
            self._last_tick_time = datetime.now(timezone.utc)
            
            # Parse tick data from SmartWebSocketV2
            tick_data = self._parse_tick(message)
            if not tick_data:
                return
            
            symbol = tick_data.get("symbol", "")
            if not symbol:
                return
            
            # Store in Redis
            store_latest_tick(symbol, tick_data)
            publish_tick(symbol, tick_data)
            
            # Update candles (synchronous, thread-safe)
            completed = self._aggregator.process_tick(symbol, tick_data)
            
            # Store completed candles
            for interval, candle in completed.items():
                store_candle(symbol, interval, candle)
            
            # Store current forming candle
            for interval in self._aggregator.INTERVALS:
                current = self._aggregator.get_current_candle(symbol, interval)
                if current:
                    store_candle(symbol, interval, current)
            
            # Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(symbol, tick_data)
                except Exception as e:
                    print(f"[MarketDataService] Callback error: {e}")
                    
        except Exception as e:
            print(f"[MarketDataService] Tick processing error: {e}")
    
    def _parse_tick(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse SmartWebSocketV2 tick message into standardized format.
        
        Handles BOTH the old documented format (symbol/ltp) AND the actual
        Angel One SmartWebSocketV2 format (token/last_traded_price in paisa).
        
        Actual SmartWebSocketV2 QUOTE mode (mode=2) returns:
        {
            "subscription_mode": 1,
            "exchange_type": 1,
            "token": "3045",
            "sequence_number": 0,
            "exchange_timestamp": 1643718000,
            "last_traded_price": 82345,    # in paisa (multiply by 0.01)
            "last_traded_qty": 100,
            "total_buy_qty": 5000,
            "total_sell_qty": 3000,
            "open_price": 82000,
            "high_price": 82500,
            "low_price": 81800,
            "close_price": 81950,
            "volume": 1234567,
            "open_interest": 0,
            "bid_price": 82340,
            "ask_price": 82350,
            "bid_qty": 100,
            "ask_qty": 100,
        }
        """
        try:
            # Detect format: check for "subscription_mode" (actual format) vs "symbol" (old format)
            if "subscription_mode" in message or "last_traded_price" in message:
                return self._parse_actual_format(message)
            
            # Old documented format
            token = message.get("token", "")
            symbol = message.get("symbol", "")
            
            if not symbol:
                return None
            
            exchange = message.get("exchange", "")
            if exchange and ":" not in symbol:
                normalized_symbol = f"{exchange}:{symbol}"
            else:
                normalized_symbol = symbol
            
            return {
                "token": token,
                "symbol": normalized_symbol,
                "exchange": exchange,
                "ltp": float(message.get("ltp", 0) or 0),
                "ltq": int(message.get("ltq", 0) or 0),
                "open": float(message.get("open", 0) or 0),
                "high": float(message.get("high", 0) or 0),
                "low": float(message.get("low", 0) or 0),
                "close": float(message.get("close", 0) or 0),
                "volume": int(message.get("volume", 0) or 0),
                "oi": int(message.get("oi", 0) or 0),
                "exchange_timestamp": message.get("exchange_timestamp", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "best_bid": float(message.get("best_bid", 0) or 0),
                "best_ask": float(message.get("best_ask", 0) or 0),
                "best_bid_qty": int(message.get("best_bid_qty", 0) or 0),
                "best_ask_qty": int(message.get("best_ask_qty", 0) or 0),
            }
        except Exception as e:
            print(f"[MarketDataService] Parse error: {e}, message: {message}")
            return None
    
    def _parse_actual_format(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse the actual Angel One SmartWebSocketV2 data format."""
        try:
            token = str(message.get("token", ""))
            exchange_type = int(message.get("exchange_type", 1))
            
            if not token:
                return None
            
            # Resolve token to symbol
            symbol = self._resolve_token_to_symbol(token, exchange_type)
            if not symbol:
                # Fallback: try to use token directly as symbol identifier
                exchange_name = self.EXCHANGE_NAMES.get(exchange_type, "NSE")
                symbol = f"{exchange_name}:UNKNOWN-{token}"
            
            # Prices are in paisa (multiply by 0.01 to get rupees)
            PAISA = 0.01
            
            ltp = (message.get("last_traded_price", 0) or 0) * PAISA
            ltq = message.get("last_traded_qty", 0) or 0
            open_p = (message.get("open_price", 0) or 0) * PAISA
            high_p = (message.get("high_price", 0) or 0) * PAISA
            low_p = (message.get("low_price", 0) or 0) * PAISA
            close_p = (message.get("close_price", 0) or 0) * PAISA
            volume = message.get("volume", 0) or 0
            oi = message.get("open_interest", 0) or 0
            
            # Bid/ask prices also in paisa
            bid_price = (message.get("bid_price", 0) or 0) * PAISA
            ask_price = (message.get("ask_price", 0) or 0) * PAISA
            bid_qty = message.get("bid_qty", 0) or 0
            ask_qty = message.get("ask_qty", 0) or 0
            
            # Timestamp
            exch_ts = message.get("exchange_timestamp", 0)
            if isinstance(exch_ts, (int, float)) and exch_ts > 0:
                # Convert from epoch seconds or milliseconds
                if exch_ts > 1e12:  # milliseconds
                    exch_ts = exch_ts / 1000
                try:
                    ts_dt = datetime.fromtimestamp(exch_ts, tz=timezone.utc)
                    ts_str = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            return {
                "token": token,
                "symbol": symbol,
                "exchange": self.EXCHANGE_NAMES.get(exchange_type, "NSE"),
                "ltp": round(ltp, 2),
                "ltq": int(ltq),
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": int(volume),
                "oi": int(oi),
                "exchange_timestamp": ts_str,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "best_bid": round(bid_price, 2),
                "best_ask": round(ask_price, 2),
                "best_bid_qty": int(bid_qty),
                "best_ask_qty": int(ask_qty),
            }
        except Exception as e:
            print(f"[MarketDataService] Actual format parse error: {e}, message: {message}")
            return None
    
    def _on_open(self, wsapp):
        """Handle WebSocket connection open."""
        print("[MarketDataService] WebSocket connected.")
        self._status = "connected"
        
        # Subscribe to all symbols
        token_list = self._build_subscription_list()
        if token_list and self._ws:
            correlation_id = "mds_sub_1"
            mode = 2  # QUOTE mode (LTP + OHLC + volume)
            self._ws.subscribe(correlation_id, mode, token_list)
            print(f"[MarketDataService] Subscribed to {len(self._subscribed_symbols)} symbols in QUOTE mode.")
    
    def _on_error(self, wsapp, error):
        """Handle WebSocket error."""
        print(f"[MarketDataService] WebSocket error: {error}")
        self._status = "error"
    
    def _on_close(self, wsapp):
        """Handle WebSocket connection close."""
        print("[MarketDataService] WebSocket closed.")
        self._status = "idle"
        self._running = False
    
    def _run_websocket(self):
        """Run WebSocket in a background thread."""
        if not HAS_SMARTWS or not SmartWebSocketV2:
            print("[MarketDataService] SmartWebSocketV2 not available.")
            self._on_error(None, "SmartWebSocketV2 not available")
            self._on_close(None)
            return
        
        client = SmartAPIManager.get_client()
        if not client or not client.jwt_token:
            print("[MarketDataService] SmartAPI not connected. Cannot start WebSocket.")
            self._on_error(None, "SmartAPI not connected")
            self._on_close(None)
            return
        
        self._smartapi_client = client
        self._status = "connecting"
        
        try:
            self._ws = SmartWebSocketV2(
                auth_token=client.jwt_token,
                api_key=client.api_key or os.getenv("SMARTAPI_API_KEY", ""),
                client_code=client.client_code or os.getenv("SMARTAPI_CLIENT_CODE", ""),
                feed_token=client.feed_token or "",
            )
            
            self._ws.on_open = self._on_open
            self._ws.on_data = self._on_data
            self._ws.on_error = self._on_error
            self._ws.on_close = self._on_close
            
            print("[MarketDataService] Connecting to SmartWebSocketV2...")
            self._ws.connect()
            
        except Exception as e:
            print(f"[MarketDataService] WebSocket connection failed: {e}")
            self._status = "error"
    
    def start(self):
        """Start the market data service."""
        if self._running:
            print("[MarketDataService] Already running.")
            return
        
        self._running = True
        self._ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self._ws_thread.start()
        print("[MarketDataService] Started.")
    
    def stop(self):
        """Stop the market data service."""
        self._running = False
        if self._ws:
            try:
                self._ws.close_connection()
            except Exception:
                pass
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5)
        self._status = "idle"
        print("[MarketDataService] Stopped.")
    
    def subscribe_symbol(self, symbol: str) -> bool:
        """Subscribe to a new symbol. Resubscribes WebSocket if connected."""
        if symbol in self._subscribed_symbols:
            return True
        
        self._subscribed_symbols.add(symbol)
        
        # If MDS was in error state due to missing auth, try to restart now
        if self._status == "error" and SmartAPIManager.is_connected():
            print(f"[MarketDataService] Restarting after auth recovery...")
            self.stop()
            self.start()
            return True
        
        # If already connected, resubscribe with new symbol
        if self._ws and self._status == "connected":
            token_list = self._build_subscription_list()
            if token_list:
                correlation_id = "mds_sub_update"
                mode = 2
                self._ws.subscribe(correlation_id, mode, token_list)
                print(f"[MarketDataService] Added {symbol} to subscription.")
        
        return True
    
    def unsubscribe_symbol(self, symbol: str) -> bool:
        """Unsubscribe from a symbol."""
        if symbol not in self._subscribed_symbols:
            return True
        
        self._subscribed_symbols.discard(symbol)
        self._aggregator.reset_symbol(symbol)
        
        # If connected, unsubscribe from specific token
        if self._ws and self._status == "connected":
            token_info = self._resolve_token(symbol)
            if token_info:
                exchange = token_info.get("exch_seg", "NSE")
                exchange_type = self.EXCHANGE_TYPES.get(exchange, 1)
                token = token_info.get("token", "")
                token_list = [{"exchangeType": exchange_type, "tokens": [token]}]
                self._ws.unsubscribe("mds_unsub", token_list)
        
        return True
    
    def add_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a callback for tick events. callback(symbol, tick_data)"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "status": self._status,
            "running": self._running,
            "smartapi_connected": self._smartapi_client is not None and self._smartapi_client.jwt_token is not None,
            "subscribed_symbols": list(self._subscribed_symbols),
            "total_ticks_received": self._total_ticks,
            "last_tick_time": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "websocket_available": HAS_SMARTWS,
        }
    
    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest tick for a symbol (from Redis or memory)."""
        tick = get_latest_tick(symbol)
        if tick:
            return tick
        return None
    
    def get_latest_candle(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Get latest candle for a symbol+interval."""
        candle = get_latest_candle(symbol, interval)
        if candle:
            return candle
        return self._aggregator.get_current_candle(symbol, interval)


async def ensure_market_data_service(symbols: List[str] = None) -> MarketDataService:
    """
    Ensure the market data service is running and subscribed to symbols.
    
    Usage:
        mds = await ensure_market_data_service(["NSE:SBIN-EQ"])
    """
    mds = MarketDataService.get_instance()
    
    # Restart if not running or stuck in error state
    if not mds._running or mds._status == "error":
        if mds._status == "error":
            mds.stop()  # Ensure clean reset before restart
        mds.start()
        # Give it a moment to connect
        await asyncio.sleep(2)
    
    if symbols:
        for symbol in symbols:
            mds.subscribe_symbol(symbol)
    
    return mds
