"""
Market – Multi-symbol data container and access layer.

The Market object is the single source of truth for all symbol data
during a backtest or research session.  Strategies receive a Market
reference on every tick so they can query prices, returns, and
historical candles for any symbol in the universe.
"""

from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Dataset-group helpers
# ---------------------------------------------------------------------------

_GROUPS_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "datasets", "groups.yaml"
)


def load_groups_config(path: str = _GROUPS_CONFIG_PATH) -> Dict[str, List[str]]:
    """Return the dataset-groups YAML as a dict (group -> [symbols])."""
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    # Flatten: remove 'custom_groups' sub-dict if present
    result: Dict[str, List[str]] = {}
    for k, v in cfg.items():
        if k == "custom_groups" and isinstance(v, dict):
            for ck, cv in (v or {}).items():
                result[ck] = list(cv or [])
        elif isinstance(v, list):
            result[k] = list(v)
    return result


def get_symbols_for_groups(groups: List[str]) -> List[str]:
    """Resolve group names to a deduplicated ordered list of symbols."""
    cfg = load_groups_config()
    seen: set = set()
    symbols: List[str] = []
    for g in groups:
        for sym in cfg.get(g, []):
            if sym not in seen:
                seen.add(sym)
                symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# Market class
# ---------------------------------------------------------------------------

class Market:
    """
    Multi-symbol market data container.

    Attributes
    ----------
    data : dict[symbol -> DataFrame]
        Each DataFrame has columns: time, open, high, low, close, volume
        with 'time' as a string formatted '%Y-%m-%d %H:%M:%S'.

    All methods are thread-safe (read-only after construction).
    """

    def __init__(self, data: Dict[str, pd.DataFrame]):
        self._lock = threading.Lock()
        # Store a clean copy of each frame indexed by time
        self._data: Dict[str, pd.DataFrame] = {}
        for sym, df in data.items():
            df = df.copy()
            if "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"], errors="coerce").dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                df = df.dropna(subset=["time"])
                df = df.sort_values("time").reset_index(drop=True)
            self._data[sym.upper()] = df

    # ── Symbol access ──────────────────────────────────────────────────────

    def get_all_symbols(self) -> List[str]:
        return list(self._data.keys())

    def get_dataframe(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._data.get(symbol.upper())

    # ── Price helpers ──────────────────────────────────────────────────────

    def get_latest_price(self, symbol: str, col: str = "close") -> Optional[float]:
        df = self.get_dataframe(symbol)
        if df is None or df.empty:
            return None
        return float(df.iloc[-1][col])

    def get_price_series(self, symbol: str, col: str = "close") -> pd.Series:
        df = self.get_dataframe(symbol)
        if df is None:
            return pd.Series(dtype=float)
        return df[col].astype(float)

    def get_price_at(self, symbol: str, timestamp: str, col: str = "close") -> Optional[float]:
        df = self.get_dataframe(symbol)
        if df is None:
            return None
        mask = df["time"] == timestamp
        rows = df[mask]
        if rows.empty:
            return None
        return float(rows.iloc[0][col])

    # ── Return helpers ─────────────────────────────────────────────────────

    def get_returns(self, symbol: str, col: str = "close") -> pd.Series:
        s = self.get_price_series(symbol, col)
        return s.pct_change().fillna(0.0)

    def get_log_returns(self, symbol: str, col: str = "close") -> pd.Series:
        s = self.get_price_series(symbol, col)
        return np.log(s / s.shift(1)).fillna(0.0)

    # ── History slicing ────────────────────────────────────────────────────

    def get_history(
        self,
        symbols: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        col: str = "close",
    ) -> pd.DataFrame:
        """
        Return a wide DataFrame (time x symbol) of close prices,
        optionally sliced by date range.
        """
        syms = symbols or self.get_all_symbols()
        frames: Dict[str, pd.Series] = {}
        for sym in syms:
            df = self.get_dataframe(sym)
            if df is None:
                continue
            s = df.set_index("time")[col].astype(float)
            if start:
                s = s[s.index >= start]
            if end:
                s = s[s.index <= end]
            frames[sym] = s
        if not frames:
            return pd.DataFrame()
        wide = pd.DataFrame(frames)
        wide.index = pd.to_datetime(wide.index, errors="coerce")
        wide = wide.sort_index()
        return wide

    # ── Correlation helpers ────────────────────────────────────────────────

    def correlation_matrix(
        self,
        symbols: Optional[List[str]] = None,
        window: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Compute Pearson correlation matrix of log-returns.
        If window is given, use only the last `window` rows.
        """
        syms = symbols or self.get_all_symbols()
        returns: Dict[str, pd.Series] = {}
        for sym in syms:
            r = self.get_log_returns(sym)
            if window:
                r = r.iloc[-window:]
            returns[sym] = r
        df = pd.DataFrame(returns).dropna()
        return df.corr()

    def rolling_correlation(
        self,
        sym1: str,
        sym2: str,
        window: int = 20,
    ) -> pd.Series:
        """Rolling Pearson correlation between two symbols."""
        r1 = self.get_log_returns(sym1)
        r2 = self.get_log_returns(sym2)
        aligned = pd.DataFrame({"a": r1.values, "b": r2.values}).dropna()
        return aligned["a"].rolling(window).corr(aligned["b"])

    # ── Volatility helpers ─────────────────────────────────────────────────

    def realized_volatility(
        self,
        symbol: str,
        window: int = 20,
        annualize: bool = True,
    ) -> pd.Series:
        """Rolling realized volatility of log-returns."""
        r = self.get_log_returns(symbol)
        rv = r.rolling(window).std()
        if annualize:
            rv = rv * np.sqrt(252)
        return rv

    # ── Spread / z-score helpers ───────────────────────────────────────────

    def spread(self, sym1: str, sym2: str, hedge_ratio: float = 1.0) -> pd.Series:
        """Price spread: sym1 - hedge_ratio * sym2."""
        p1 = self.get_price_series(sym1)
        p2 = self.get_price_series(sym2)
        n = min(len(p1), len(p2))
        return (p1.iloc[-n:].values - hedge_ratio * p2.iloc[-n:].values)

    def z_score(self, series: pd.Series, window: int = 20) -> pd.Series:
        """Rolling z-score of a series."""
        mu = series.rolling(window).mean()
        sigma = series.rolling(window).std()
        return (series - mu) / sigma.replace(0, np.nan)

    # ── Repr ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Market symbols={self.get_all_symbols()} bars={[len(v) for v in self._data.values()]}>"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def market_from_dict(data: Dict[str, pd.DataFrame]) -> Market:
    """Create a Market from an existing symbol -> DataFrame mapping."""
    return Market(data)


def market_from_groups(groups: List[str], loader_fn) -> Market:
    """
    Create a Market by resolving group names and calling loader_fn(symbols).

    loader_fn must accept List[str] and return Dict[str, DataFrame].
    """
    symbols = get_symbols_for_groups(groups)
    data = loader_fn(symbols)
    return Market(data)
