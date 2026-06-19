"""
PnLSnapshotScheduler: Configurable periodic PnL snapshot generation.

Generates PnL snapshots at:
- Configurable time intervals (e.g., every 30s, 60s, 5m)
- On significant portfolio events (trade fills, margin calls, large PnL changes)
- NOT on every single tick cycle

Reduces database load by throttling snapshot persistence while still capturing
meaningful portfolio state changes.
"""

import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from engine.portfolio import PortfolioManager


@dataclass
class PnLSnapshotConfig:
    """Configuration for PnL snapshot scheduling."""
    interval_seconds: float = 30.0  # Regular snapshot interval
    on_trade_fill: bool = True     # Snapshot on every trade fill
    on_margin_call: bool = True     # Snapshot on margin call
    pnl_change_threshold_pct: float = 0.5  # Snapshot if PnL changes by this %
    max_snapshots_per_minute: int = 10  # Rate limit


class PnLSnapshotScheduler:
    """
    Schedules PnL snapshot generation intelligently.
    
    Instead of persisting on every tick, this scheduler decides whether
    a snapshot is worth taking based on time and significance thresholds.
    """
    
    def __init__(
        self,
        portfolio_mgr: PortfolioManager,
        config: Optional[PnLSnapshotConfig] = None,
    ):
        self.portfolio_mgr = portfolio_mgr
        self.config = config or PnLSnapshotConfig()
        self._last_snapshot_time: float = 0.0
        self._last_snapshot_equity: float = portfolio_mgr.portfolio.equity
        self._last_snapshot_total_pnl: float = portfolio_mgr.portfolio.total_pnl
        self._snapshot_count_this_minute: int = 0
        self._minute_start: float = time.time()
    
    def should_snapshot(self, event_type: str = "tick", event_payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine whether a PnL snapshot should be taken now.
        
        Args:
            event_type: "tick", "trade_fill", "margin_call", "manual_order"
            event_payload: optional data about the event
            
        Returns:
            True if a snapshot should be taken, False otherwise
        """
        now = time.time()
        
        # Reset per-minute counter
        if now - self._minute_start >= 60.0:
            self._snapshot_count_this_minute = 0
            self._minute_start = now
        
        # Rate limit check
        if self._snapshot_count_this_minute >= self.config.max_snapshots_per_minute:
            return False
        
        # Always snapshot on margin call
        if event_type == "margin_call" and self.config.on_margin_call:
            return True
        
        # Snapshot on trade fills if configured
        if event_type == "trade_fill" and self.config.on_trade_fill:
            return True
        
        # Snapshot on manual orders (treat as trade fill for scheduling)
        if event_type == "manual_order" and self.config.on_trade_fill:
            return True
        
        # Time-based interval check
        if now - self._last_snapshot_time >= self.config.interval_seconds:
            return True
        
        # Significant PnL change check
        current_equity = self.portfolio_mgr.portfolio.equity
        current_pnl = self.portfolio_mgr.portfolio.total_pnl
        
        if self._last_snapshot_equity > 0:
            equity_change_pct = abs(current_equity - self._last_snapshot_equity) / self._last_snapshot_equity * 100
            if equity_change_pct >= self.config.pnl_change_threshold_pct:
                return True
        
        pnl_change = abs(current_pnl - self._last_snapshot_total_pnl)
        if self._last_snapshot_equity > 0:
            pnl_change_pct = pnl_change / self._last_snapshot_equity * 100
            if pnl_change_pct >= self.config.pnl_change_threshold_pct:
                return True
        
        return False
    
    def build_snapshot(self) -> Dict[str, Any]:
        """
        Build a PnL snapshot dict from the current portfolio state.
        
        Returns:
            Dict ready for persistence service
        """
        snapshot = self.portfolio_mgr.get_snapshot()
        positions = self.portfolio_mgr.portfolio.positions
        
        positions_json = {
            sym: {
                "qty": pos.qty,
                "avg_price": pos.avg_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
            }
            for sym, pos in positions.items()
        }
        
        result = {
            "cash": snapshot["cash"],
            "equity": snapshot["equity"],
            "unrealized_pnl": snapshot.get("unrealized_pnl", 0.0),
            "realized_pnl": sum(p.realized_pnl for p in positions.values()),
            "total_fees": snapshot["total_fees"],
            "total_pnl": snapshot["total_pnl"],
            "margin_used": snapshot.get("margin_used", 0.0),
            "margin_free": snapshot.get("margin_free", 0.0),
            "position_count": len(positions),
            "total_qty": sum(abs(p.qty) for p in positions.values()),
            "positions": positions_json,
        }
        
        return result
    
    def record_snapshot_taken(self):
        """Call after a snapshot is persisted to update internal state."""
        self._last_snapshot_time = time.time()
        self._last_snapshot_equity = self.portfolio_mgr.portfolio.equity
        self._last_snapshot_total_pnl = self.portfolio_mgr.portfolio.total_pnl
        self._snapshot_count_this_minute += 1
    
    def reset(self):
        """Reset scheduler state (e.g., on deployment reset)."""
        self._last_snapshot_time = 0.0
        self._last_snapshot_equity = self.portfolio_mgr.portfolio.equity
        self._last_snapshot_total_pnl = self.portfolio_mgr.portfolio.total_pnl
        self._snapshot_count_this_minute = 0
        self._minute_start = time.time()
