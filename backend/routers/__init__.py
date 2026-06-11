"""
Router aggregation for clean imports in main.py.
"""

from backend.routers import auth, data, strategies, backtest, research

__all__ = ["auth", "data", "strategies", "backtest", "research"]
