"""
MarketInterface – Thread-safe, cursor-aware view over the Market object.

During a backtest the engine advances one bar at a time.  The MarketInterface
wraps the full Market and exposes only data up to the current timestamp,
so strategies cannot accidentally look into the future.

Used internally by BacktestEngine when running MultiAssetStrategy instances.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

import pandas as pd

from engine.market import Market


class MarketInterface:
    """
    A thread-safe, time-sliced view over the Market object.

    The engine calls advance(timestamp) before dispatching each bar to the
    strategy.  All data-access methods return only rows with time <= current_time.
    """

    def __init__(self, market: Market):
        self._market = market
        self._current_time: Optional[str] = None
        self._lock = threading.RLock()
        # Cache sliced frames per timestamp to avoid re-slicing on every call
        self._cache: Dict[str, Dict[str, pd.DataFrame]] = {}

    # ── Engine API ────────────────────────────────────────────────────────

    def advance(self, timestamp: str) -> None:
        """Move the cursor forward to `timestamp` (called by the engine)."""
        with self._lock:
            self._current_time = timestamp

    def reset(self) -> None:
        """Reset cursor and flush cache (called between runs)."""
        with self._lock:
            self._current_time = None
            self._cache.clear()

    # ── Strategy-facing API ───────────────────────────────────────────────

    def get_all_symbols(self) -> List[str]:
        return self._market.get_all_symbols()

    def get_close(self, symbol: str) -> Optional[float]:
        """Latest close price up to current_time."""
        with self._lock:
            df = self._sliced(symbol)
            if df is None or df.empty:
                return None
            return float(df["close"].iloc[-1])

    def get_ohlcv(self, symbol: str) -> Optional[Dict[str, float]]:
        """Latest OHLCV bar up to current_time."""
        with self._lock:
            df = self._sliced(symbol)
            if df is None or df.empty:
                return None
            row = df.iloc[-1]
            return {
                "time": str(row.get("time", self._current_time)),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
            }

    def get_history(
        self,
        symbol: str,
        n: int = 50,
        col: str = "close",
    ) -> pd.Series:
        """Return the last `n` values of `col` for `symbol` up to current_time."""
        with self._lock:
            df = self._sliced(symbol)
            if df is None or df.empty:
                return pd.Series(dtype=float)
            return df[col].astype(float).iloc[-n:]

    def get_returns(self, symbol: str, n: int = 50) -> pd.Series:
        """Percentage returns for the last n bars."""
        prices = self.get_history(symbol, n + 1)
        return prices.pct_change().dropna()

    def correlation_matrix(
        self,
        symbols: Optional[List[str]] = None,
        window: int = 20,
    ) -> pd.DataFrame:
        """Correlation matrix of log-returns up to current_time."""
        syms = symbols or self.get_all_symbols()
        returns: Dict[str, pd.Series] = {}
        with self._lock:
            for sym in syms:
                df = self._sliced(sym)
                if df is None or len(df) < 2:
                    continue
                closes = df["close"].astype(float)
                log_rets = (closes / closes.shift(1)).apply(
                    lambda x: float("nan") if x <= 0 else x
                ).pipe(lambda s: s.map(lambda v: v if v == v else 0.0))
                import numpy as np
                log_rets = (closes.pct_change()).iloc[-window:]
                returns[sym] = log_rets
        if not returns:
            return pd.DataFrame()
        aligned = pd.DataFrame(returns).dropna()
        return aligned.corr()

    # ── Internals ─────────────────────────────────────────────────────────

    def _sliced(self, symbol: str) -> Optional[pd.DataFrame]:
        """Return the dataframe for `symbol` filtered to <= current_time."""
        sym = symbol.upper()
        ts = self._current_time

        if ts is None:
            return self._market.get_dataframe(sym)

        # Check cache
        if ts in self._cache and sym in self._cache[ts]:
            return self._cache[ts][sym]

        df = self._market.get_dataframe(sym)
        if df is None:
            return None

        if "time" not in df.columns:
            return df

        sliced = df[df["time"] <= ts]

        if ts not in self._cache:
            self._cache[ts] = {}
        # Limit cache to last 3 timestamps to avoid unbounded growth
        if len(self._cache) > 3:
            oldest = min(self._cache.keys())
            del self._cache[oldest]

        self._cache[ts][sym] = sliced
        return sliced

    # ── Repr ──────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"<MarketInterface symbols={self.get_all_symbols()} "
            f"cursor={self._current_time}>"
        )
