"""
Prosperity-compatible runtime datamodels.

Defines the contract between the backtester and user strategies:
- OrderDepth: market microstructure (bid/ask levels)
- TradingState: complete market state per tick (orders, trades, positions, observations)
- Logger: structured logging with JSON flush
- Trade, Order, Listing: transaction and instrument metadata
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import json


class OrderType(str, Enum):
    """Order types in Prosperity."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """A single order submitted by the strategy."""
    symbol: str
    direction: str  # "BUY" or "SELL"
    price: float
    quantity: int
    order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderDepth:
    """Order book snapshot: bid and ask levels with sizes."""
    symbol: str
    bid_prices: List[int]        # Price levels, best (highest) first
    bid_volumes: List[int]       # Corresponding bid quantities
    ask_prices: List[int]        # Price levels, best (lowest) first
    ask_volumes: List[int]       # Corresponding ask quantities

    def best_bid(self) -> Optional[Tuple[int, int]]:
        """Return (price, volume) of best bid, or None if no bids."""
        if self.bid_prices:
            return (self.bid_prices[0], self.bid_volumes[0])
        return None

    def best_ask(self) -> Optional[Tuple[int, int]]:
        """Return (price, volume) of best ask, or None if no asks."""
        if self.ask_prices:
            return (self.ask_prices[0], self.ask_volumes[0])
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON logging."""
        return {
            "symbol": self.symbol,
            "bid_prices": self.bid_prices,
            "bid_volumes": self.bid_volumes,
            "ask_prices": self.ask_prices,
            "ask_volumes": self.ask_volumes,
        }


@dataclass
class Trade:
    """A trade (own execution or market trade)."""
    symbol: str
    price: float
    quantity: int
    timestamp: str
    direction: str  # "BUY" or "SELL"
    trade_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Position:
    """Current position in a symbol."""
    symbol: str
    quantity: int  # Positive = long, negative = short
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Listing:
    """Instrument metadata (optional; for future use)."""
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    segment: Optional[str] = None  # "EQUITY", "FUTURES", etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Observation:
    """Observations about market state (custom strategy data)."""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"data": self.data}


@dataclass
class TradingState:
    """
    Complete market state snapshot for a single tick.
    
    This is the interface between the backtester and user strategy.
    Replaces raw DataFrame rows and provides structured access to
    orders, trades, positions, and observations.
    """
    timestamp: str
    order_depths: Dict[str, OrderDepth]      # Symbol -> order book
    own_trades: Dict[str, List[Trade]]       # Symbol -> trades by this strategy
    market_trades: Dict[str, List[Trade]]    # Symbol -> all market trades
    positions: Dict[str, Position]           # Symbol -> current position
    portfolio_value: float                   # Total equity
    cash: float                              # Available cash
    trader_data: str                         # JSON-serialized strategy memory
    listings: Dict[str, Listing] = field(default_factory=dict)  # Instrument metadata
    observations: Dict[str, Observation] = field(default_factory=dict)  # Custom data

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging."""
        return {
            "timestamp": self.timestamp,
            "order_depths": {k: v.to_dict() for k, v in self.order_depths.items()},
            "own_trades": {k: [t.to_dict() for t in trades] for k, trades in self.own_trades.items()},
            "market_trades": {k: [t.to_dict() for t in trades] for k, trades in self.market_trades.items()},
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "portfolio_value": self.portfolio_value,
            "cash": self.cash,
            "trader_data": self.trader_data,
            "listings": {k: v.to_dict() for k, v in self.listings.items()},
            "observations": {k: v.to_dict() for k, v in self.observations.items()},
        }


class Logger:
    """
    Structured logging for strategies.
    
    Captures logs as JSON and flushes them to a list.
    Used by strategies to record decisions and debug info.
    """

    def __init__(self):
        self._logs: List[Dict[str, Any]] = []

    def print(self, message: str, **kwargs):
        """Log a message with optional metadata."""
        entry = {
            "type": "print",
            "message": message,
            **kwargs,
        }
        self._logs.append(entry)

    def record(self, event_type: str, **data):
        """Record a structured event."""
        entry = {
            "type": event_type,
            **data,
        }
        self._logs.append(entry)

    def flush(self) -> str:
        """
        Flush logs as a single JSON-encoded string.
        
        Returns: JSON-encoded list of log entries (compressed format).
        """
        result = json.dumps(self._logs, separators=(',', ':'), default=str)
        self._logs.clear()
        return result

    def get_logs(self) -> List[Dict[str, Any]]:
        """Get raw logs without clearing."""
        return list(self._logs)

    def clear(self):
        """Clear logs without flushing."""
        self._logs.clear()
