"""
Sizing service: position sizing calculations.

Centralizes risk-based and margin-based position sizing that was
duplicated across the dataset endpoint and backtest endpoint.
"""

from typing import Optional, Tuple
import pandas as pd


def calculate_suggested_position_size(
    price_series: pd.Series,
    initial_capital: float = 100000.0,
    trade_type: str = "INTRADAY",
    risk_pct: float = 0.02,
) -> int:
    """
    Calculate a suggested max position size based on volatility and margin.
    
    Args:
        price_series: recent close prices (e.g. last 100 bars)
        initial_capital: starting capital
        trade_type: INTRADAY, DELIVERY, or FUTURES
        risk_pct: risk per trade as decimal (default 2%)
        
    Returns:
        suggested max position size (shares/contracts)
    """
    avg_price = float(price_series.mean()) if not price_series.empty else 0
    price_std = float(price_series.std()) if len(price_series) > 1 else avg_price * 0.02
    
    risk_amount = initial_capital * risk_pct
    stop_distance = max(price_std * 2, avg_price * 0.005)
    risk_based_size = int(risk_amount / stop_distance) if stop_distance > 0 else 1
    
    margin_mult = 0.20 if trade_type == "INTRADAY" else (0.15 if trade_type == "FUTURES" else 1.0)
    leverage = 1.0 / margin_mult if margin_mult > 0 else 1.0
    margin_based_size = int(initial_capital * leverage / avg_price) if avg_price > 0 else 1
    
    suggested = min(risk_based_size, int(margin_based_size * 0.20))
    return max(suggested, 1)


def calculate_backtest_max_position(
    df: pd.DataFrame,
    initial_capital: float,
    trade_type: str,
    requested_max: Optional[int] = None,
) -> int:
    """
    Calculate final max position size for a backtest.
    
    Uses auto-calculated sizing unless user provided an explicit value.
    
    Args:
        df: price DataFrame
        initial_capital: starting capital
        trade_type: INTRADAY, DELIVERY, or FUTURES
        requested_max: user-provided max position size (None = auto)
        
    Returns:
        final max position size
    """
    if requested_max and requested_max > 0:
        return requested_max
    
    close_series = df['close'].iloc[-100:] if not df.empty else pd.Series(dtype=float)
    return calculate_suggested_position_size(
        price_series=close_series,
        initial_capital=initial_capital,
        trade_type=trade_type,
    )
