"""
QuantLab unified trading strategy runtime.

Defines the contract between backtester and user strategies:
- OrderDepth: market microstructure (bid/ask levels)
- TradingState: complete market state per tick
- Logger: structured logging with JSON flush
- Unified runtime for all strategy types
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import json


class OrderType(str, Enum):
    """Order types."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """A single order submitted by the strategy.

    Supports both constructor styles:
      - Standard: Order(symbol, direction, price, quantity)
      - Prosperity: Order(symbol, price, quantity)  # direction inferred from qty sign
    """
    symbol: str
    direction: str = ""  # "BUY" or "SELL"
    price: float = 0.0
    quantity: int = 0
    type: str = "LIMIT"
    order_id: Optional[str] = None

    def __post_init__(self):
        # If direction is missing, this was called Prosperity-style:
        # Order(symbol, price, quantity) where positive qty = BUY
        if not self.direction or self.direction not in ("BUY", "SELL"):
            # direction got the price value, price got the quantity
            try:
                qty = int(self.price)
                self.price = float(self.direction) if self.direction else 0.0
                self.direction = "BUY" if qty >= 0 else "SELL"
                self.quantity = abs(qty)
            except (ValueError, TypeError):
                self.direction = "BUY"
                self.quantity = abs(self.quantity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "price": self.price,
            "quantity": self.quantity,
            "type": self.type,
            "order_id": self.order_id,
        }


@dataclass
class OrderDepth:
    """Order book snapshot: bid and ask levels with sizes."""
    symbol: str
    bid_prices: List[int]        # Price levels, best (highest) first
    bid_volumes: List[int]       # Corresponding bid quantities
    ask_prices: List[int]        # Price levels, best (lowest) first
    ask_volumes: List[int]       # Corresponding ask quantities

    @property
    def buy_orders(self) -> Dict[int, int]:
        """Prosperity-compatible: {price: volume} for bids."""
        return {p: v for p, v in zip(self.bid_prices, self.bid_volumes)}

    @property
    def sell_orders(self) -> Dict[int, int]:
        """Prosperity-compatible: {price: volume} for asks."""
        return {p: v for p, v in zip(self.ask_prices, self.ask_volumes)}

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
    """Instrument metadata."""
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    segment: Optional[str] = None  # "EQUITY", "FUTURES", etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Observation:
    """Custom observations about market state."""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"data": self.data}


@dataclass
class TradingState:
    """
    Complete market state snapshot for a single tick.
    
    This is the unified interface between backtester and strategy.
    Provides structured access to orders, trades, positions, and market data.
    """
    timestamp: str
    order_depths: Dict[str, OrderDepth]      # Symbol -> order book
    own_trades: Dict[str, List[Trade]]       # Symbol -> trades by this strategy
    market_trades: Dict[str, List[Trade]]    # Symbol -> all market trades
    positions: Dict[str, Position]           # Symbol -> current position
    portfolio_value: float                   # Total equity
    cash: float                              # Available cash
    trader_data: str                         # JSON-serialized strategy memory (persisted across ticks)
    listings: Dict[str, Listing] = field(default_factory=dict)
    observations: Dict[str, Observation] = field(default_factory=dict)

    @property
    def position(self) -> Dict[str, int]:
        """Prosperity-compatible: {symbol: quantity} mapping."""
        return {sym: pos.quantity for sym, pos in self.positions.items()}

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
    
    Captures logs as JSON and flushes them as a compressed JSON line.
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
        Flush logs as a single JSON-encoded string (compressed format).
        
        Returns: JSON-encoded list of log entries.
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
