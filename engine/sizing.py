"""
Position Sizing Framework.

Supported methods:
- fixed_qty         : fixed number of shares
- fixed_capital     : allocate a fixed ₹ amount
- pct_capital       : percentage of total portfolio capital
- atr_based         : risk a fixed ₹ amount per ATR
- volatility_adjusted : scale by inverse realized volatility
- kelly             : fractional Kelly criterion
- risk_parity       : equal risk contribution across N assets
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Individual sizing methods
# ---------------------------------------------------------------------------


def fixed_qty(qty: int, **_) -> int:
    """Return the specified fixed quantity."""
    return max(1, int(qty))


def fixed_capital(
    capital: float,
    price: float,
    **_,
) -> int:
    """Allocate a fixed ₹ capital amount → quantity at current price."""
    if price <= 0:
        return 0
    return max(1, int(capital / price))


def pct_capital(
    portfolio_value: float,
    pct: float,
    price: float,
    **_,
) -> int:
    """Allocate `pct` % of total portfolio to this position."""
    allocated = portfolio_value * pct / 100.0
    if price <= 0:
        return 0
    return max(1, int(allocated / price))


def atr_based(
    risk_per_trade: float,
    atr: float,
    atr_multiplier: float = 1.0,
    **_,
) -> int:
    """
    Risk `risk_per_trade` ₹ with stop at `atr_multiplier * ATR` away from entry.
    qty = risk_per_trade / (atr_multiplier * atr)
    """
    stop_distance = atr * atr_multiplier
    if stop_distance <= 0:
        return 0
    return max(1, int(risk_per_trade / stop_distance))


def volatility_adjusted(
    capital: float,
    target_vol: float,
    realized_vol: float,
    price: float,
    **_,
) -> int:
    """
    Scale position so realized volatility matches target_vol.
    qty ∝ target_vol / realized_vol.
    """
    if realized_vol <= 0 or price <= 0:
        return 0
    notional = capital * (target_vol / realized_vol)
    return max(1, int(notional / price))


def kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    portfolio_value: float,
    price: float,
    fraction: float = 0.5,
    **_,
) -> int:
    """
    Fractional Kelly criterion.
    f = fraction * (win_rate / |avg_loss| - (1 - win_rate) / avg_win)
    """
    if avg_win <= 0 or avg_loss >= 0:
        return 0
    f = fraction * (win_rate / abs(avg_loss) - (1 - win_rate) / avg_win)
    f = max(0.0, min(f, 1.0))  # clamp to [0, 1]
    notional = portfolio_value * f
    if price <= 0:
        return 0
    return max(1, int(notional / price))


def risk_parity(
    portfolio_value: float,
    prices: Dict[str, float],
    vols: Dict[str, float],
    **_,
) -> Dict[str, int]:
    """
    Equal risk contribution across all symbols.
    Returns a dict of symbol -> quantity.

    vol_i is the annualised realized volatility of symbol i.
    """
    symbols = list(prices.keys())
    vols_arr = np.array([vols.get(s, 0.01) for s in symbols])
    vols_arr = np.where(vols_arr <= 0, 0.01, vols_arr)

    inv_vol = 1.0 / vols_arr
    weights = inv_vol / inv_vol.sum()  # normalize to sum to 1

    result: Dict[str, int] = {}
    for i, sym in enumerate(symbols):
        allocated = portfolio_value * weights[i]
        p = prices.get(sym, 0.0)
        result[sym] = max(1, int(allocated / p)) if p > 0 else 0
    return result


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------


def size_position(
    method: str,
    **kwargs: Any,
) -> int:
    """
    Unified position-sizing entry point.

    Parameters
    ----------
    method : str
        One of 'fixed_qty', 'fixed_capital', 'pct_capital', 'atr_based',
        'volatility_adjusted', 'kelly'.
    **kwargs : passed to the underlying sizing function.

    Returns
    -------
    int : number of shares / units to trade
    """
    method = method.lower().strip()
    dispatch = {
        "fixed_qty": fixed_qty,
        "fixed_capital": fixed_capital,
        "pct_capital": pct_capital,
        "atr_based": atr_based,
        "volatility_adjusted": volatility_adjusted,
        "kelly": kelly,
    }
    fn = dispatch.get(method)
    if fn is None:
        raise ValueError(f"Unknown sizing method '{method}'. Choose from: {list(dispatch)}")
    return fn(**kwargs)
