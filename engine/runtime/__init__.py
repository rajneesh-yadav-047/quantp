"""
Runtime package: strategy execution, datamodels, and adapters.

Provides Prosperity-compatible runtime contract with backward compatibility
for legacy on_bar strategies.
"""

from engine.runtime.datamodels import (
    Order,
    OrderDepth,
    Trade,
    Position,
    Listing,
    Observation,
    TradingState,
    Logger,
    OrderType,
)

from engine.runtime.adapters import (
    CandleToOrderBookAdapter,
    PortfolioStateBuilder,
    ReplayEventBuilder,
)

__all__ = [
    "Order",
    "OrderDepth",
    "Trade",
    "Position",
    "Listing",
    "Observation",
    "TradingState",
    "Logger",
    "OrderType",
    "CandleToOrderBookAdapter",
    "PortfolioStateBuilder",
    "ReplayEventBuilder",
]
