"""
Replay logger: generates JSONL replay events for frontend consumption.

Decoupled from BacktestEngine so logging can be tested independently
and potentially swapped for other output formats.
"""

import json
import os
from typing import Dict, Any, List, Optional
from engine.runtime.datamodels import TradingState


class ReplayLogger:
    """
    Writes structured replay events to a JSONL file.
    
    Each line is a JSON object representing one tick of the backtest,
    containing candles, orders, fills, portfolio state, and strategy logs.
    """

    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        self._file = open(log_file_path, "w")

    def write_event(self, event: Dict[str, Any]) -> None:
        """Write a single replay event as one JSONL line."""
        self._file.write(json.dumps(event, separators=(',', ':'), default=str) + "\n")

    def close(self) -> None:
        """Close the log file."""
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @staticmethod
    def build_event(
        step: int,
        timestamp: str,
        trading_state: TradingState,
        orders_submitted: List[Dict[str, Any]],
        orders_filled: List[Dict[str, Any]],
        strategy_logs: str = "",
        portfolio_snapshot: Optional[Dict[str, Any]] = None,
        current_candles: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a single replay event matching the frontend's expected format.
        """
        # Parse strategy_logs JSON string into log_messages array
        log_messages: List[str] = []
        if strategy_logs:
            try:
                logs = json.loads(strategy_logs)
                if isinstance(logs, list):
                    for entry in logs:
                        if isinstance(entry, dict):
                            msg = entry.get("message", "")
                            if msg:
                                log_messages.append(msg)
                        elif isinstance(entry, str):
                            log_messages.append(entry)
            except Exception:
                pass

        # Build candle dict from current_candles or derive from order_depths
        candle: Dict[str, Any] = {}
        if current_candles:
            for sym, row in current_candles.items():
                candle[sym] = {
                    "open": float(row.get("open", row.get("close", 0))),
                    "high": float(row.get("high", row.get("close", 0))),
                    "low": float(row.get("low", row.get("close", 0))),
                    "close": float(row.get("close", 0)),
                    "volume": int(row.get("volume", 0)),
                }
        else:
            for sym, od in trading_state.order_depths.items():
                best_bid = od.bid_prices[0] if od.bid_prices else 0
                best_ask = od.ask_prices[0] if od.ask_prices else 0
                mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
                candle[sym] = {
                    "open": mid,
                    "high": mid,
                    "low": mid,
                    "close": mid,
                    "volume": od.bid_volumes[0] + od.ask_volumes[0] if od.bid_volumes and od.ask_volumes else 0,
                }

        # Build order_depths snapshot
        order_depths_snapshot = {}
        for sym, od in trading_state.order_depths.items():
            order_depths_snapshot[sym] = od.to_dict()

        # Portfolio snapshot
        pf = portfolio_snapshot or {
            "cash": trading_state.cash,
            "margin_used": 0.0,
            "margin_free": trading_state.cash,
            "equity": trading_state.portfolio_value,
            "unrealized_pnl": 0.0,
            "total_fees": 0.0,
            "total_pnl": 0.0,
            "positions": {
                sym: {
                    "symbol": sym,
                    "qty": pos.quantity,
                    "avg_price": pos.avg_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                }
                for sym, pos in trading_state.positions.items()
            },
        }

        return {
            "step": step,
            "timestamp": timestamp,
            "candle": candle,
            "order_depths": order_depths_snapshot,
            "orders_submitted": orders_submitted,
            "orders_filled": orders_filled,
            "portfolio": pf,
            "log_messages": log_messages,
        }
