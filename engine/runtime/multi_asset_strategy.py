"""
Multi-Asset Strategy Base Class.

Strategies that trade multiple symbols simultaneously should inherit from
MultiAssetStrategy.  The engine calls on_tick(market_state) each bar and
the strategy uses the helper methods below to query prices, history, and
submit orders.

Legacy single-symbol on_bar strategies continue to work unchanged via the
existing LegacyRuntime.
"""

from __future__ import annotations

import abc
import json
from typing import Any, Dict, List, Optional

from engine.datamodels import Candle, MarketState


class Order:
    """Simple order object submitted by a multi-asset strategy."""

    def __init__(
        self,
        symbol: str,
        direction: str,       # "BUY" | "SELL"
        quantity: int,
        price: Optional[float] = None,   # None = market order
        order_type: str = "MARKET",      # "MARKET" | "LIMIT"
        tag: str = "",
    ):
        self.symbol = symbol.upper()
        self.direction = direction.upper()
        self.quantity = abs(int(quantity))
        self.price = price
        self.order_type = order_type
        self.tag = tag

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type,
            "tag": self.tag,
        }


class MultiAssetStrategy(abc.ABC):
    """
    Base class for strategies that trade multiple symbols.

    Sub-classes must implement on_tick().  They can call:
      - self.price(symbol)          → latest close price
      - self.history(symbol, n)     → list of last n Candle objects
      - self.position(symbol)       → current net position qty (int)
      - self.cash                   → portfolio cash
      - self.equity                 → portfolio equity
      - self.order(symbol, dir, qty, price=None) → submit an order
      - self.cancel_all(symbol)     → cancel pending orders for symbol
      - self.log(msg)               → log a message
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        self.parameters: Dict[str, Any] = parameters or {}
        self._market_state: Optional[MarketState] = None
        self._submitted_orders: List[Order] = []
        self._logs: List[str] = []

    # ── Abstract interface ─────────────────────────────────────────────────

    @abc.abstractmethod
    def on_tick(self, market_state: MarketState) -> None:
        """Called every bar.  Implement your strategy logic here."""

    # ── Helper accessors ───────────────────────────────────────────────────

    def price(self, symbol: str, field: str = "close") -> float:
        """Return the latest price for a symbol."""
        if self._market_state is None:
            return 0.0
        candle = self._market_state.current_candle.get(symbol.upper())
        if candle is None:
            return 0.0
        return getattr(candle, field, candle.close)

    def history(self, symbol: str, n: int = 50) -> List[Candle]:
        """Return the last n candles for a symbol."""
        if self._market_state is None:
            return []
        candles = self._market_state.historical_candles.get(symbol.upper(), [])
        return candles[-n:]

    def position(self, symbol: str) -> int:
        """Return the current net position quantity for a symbol (+ve long, -ve short)."""
        if self._market_state is None:
            return 0
        pos = self._market_state.positions.get(symbol.upper())
        if pos is None:
            return 0
        return int(getattr(pos, "qty", 0))

    @property
    def cash(self) -> float:
        if self._market_state is None:
            return 0.0
        return float(self._market_state.portfolio.cash)

    @property
    def equity(self) -> float:
        if self._market_state is None:
            return 0.0
        return float(self._market_state.portfolio.equity)

    def symbols(self) -> List[str]:
        """All symbols active in the current bar."""
        if self._market_state is None:
            return []
        return list(self._market_state.current_candle.keys())

    # ── Order submission ───────────────────────────────────────────────────

    def order(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        price: Optional[float] = None,
        tag: str = "",
    ) -> None:
        """Submit an order.  Called from on_tick."""
        if quantity <= 0:
            return
        self._submitted_orders.append(
            Order(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                price=price,
                order_type="LIMIT" if price else "MARKET",
                tag=tag,
            )
        )

    def buy(self, symbol: str, quantity: int, price: Optional[float] = None, tag: str = "") -> None:
        self.order(symbol, "BUY", quantity, price, tag)

    def sell(self, symbol: str, quantity: int, price: Optional[float] = None, tag: str = "") -> None:
        self.order(symbol, "SELL", quantity, price, tag)

    # ── Logging ────────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        self._logs.append(str(msg))

    # ── Engine interface (called by runtime) ───────────────────────────────

    def _set_state(self, state: MarketState) -> None:
        self._market_state = state
        self._submitted_orders = []
        self._logs = []

    def _run_tick(self, state: MarketState):
        self._set_state(state)
        self.on_tick(state)
        return self._submitted_orders, json.dumps(self._logs)

    def get_logs(self) -> str:
        return json.dumps(self._logs)
