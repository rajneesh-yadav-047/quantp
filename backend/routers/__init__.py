"""
Router aggregation for clean imports in main.py.
"""

from backend.routers import auth, data, strategies, backtest, research, deployments, live_trading, groups

__all__ = ["auth", "data", "strategies", "backtest", "research", "deployments", "live_trading", "groups"]
