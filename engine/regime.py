"""
Regime Detection Framework.

Classifies every bar into one of five market regimes:
  - TRENDING_BULLISH
  - TRENDING_BEARISH
  - BREAKOUT
  - HIGH_VOLATILITY
  - LOW_VOLATILITY  (replaces QUIET_RANGING)
  - VOLATILE_RANGING
  - QUIET_RANGING   (legacy fallback)

Uses: ATR, Realized Volatility, ADX proxy, Volume Expansion, Return Autocorrelation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class Regime(str, Enum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    BREAKOUT = "BREAKOUT"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    VOLATILE_RANGING = "VOLATILE_RANGING"
    QUIET_RANGING = "QUIET_RANGING"
    GAP_DAY = "GAP_DAY"


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute a simplified ADX proxy."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(period).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_di = (
        pd.Series(plus_dm, index=df.index).rolling(period).mean()
        / atr.replace(0, np.nan)
        * 100
    )
    minus_di = (
        pd.Series(minus_dm, index=df.index).rolling(period).mean()
        / atr.replace(0, np.nan)
        * 100
    )
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.rolling(period).mean()
    return adx.bfill()


def classify_regimes(
    df: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
    atr_period: int = 14,
    vol_period: int = 20,
    adx_threshold: float = 25.0,
    vol_high_quantile: float = 0.75,
    vol_low_quantile: float = 0.25,
    breakout_atr_mult: float = 1.5,
) -> pd.DataFrame:
    """
    Classify each bar of `df` into a Regime.

    Required columns: open, high, low, close, volume.

    Parameters
    ----------
    df : DataFrame with OHLCV columns
    fast_period : EMA fast window
    slow_period : EMA slow window
    atr_period  : ATR window
    vol_period  : realized-volatility window
    adx_threshold : ADX above this => trending
    vol_high_quantile : vol percentile above which = HIGH_VOLATILITY
    vol_low_quantile  : vol percentile below which = LOW_VOLATILITY
    breakout_atr_mult : bar range > mult * ATR => BREAKOUT

    Returns
    -------
    df with added columns: ema_fast, ema_slow, atr, adx_proxy,
    realized_vol, vol_regime, regime
    """
    df = df.copy()
    if "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

    # EMAs
    df["ema_fast"] = close.ewm(span=fast_period, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=slow_period, adjust=False).mean()

    # ATR
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    df["atr"] = tr.rolling(atr_period).mean().bfill()

    # ADX proxy
    df["adx_proxy"] = _compute_adx(df, atr_period)

    # Realized volatility (annualised)
    log_rets = np.log(close / close.shift(1)).fillna(0.0)
    df["realized_vol"] = log_rets.rolling(vol_period).std() * np.sqrt(252)
    vol_high = df["realized_vol"].quantile(vol_high_quantile)
    vol_low = df["realized_vol"].quantile(vol_low_quantile)
    df["vol_regime"] = "NORMAL"
    df.loc[df["realized_vol"] > vol_high, "vol_regime"] = "HIGH"
    df.loc[df["realized_vol"] < vol_low, "vol_regime"] = "LOW"

    # Volume expansion
    avg_volume = volume.rolling(vol_period).mean()
    volume_expansion = volume > (avg_volume * 1.5)

    # Return autocorrelation
    autocorr = log_rets.rolling(vol_period).apply(
        lambda x: pd.Series(x).autocorr(lag=1) if len(x) > 5 else 0.0,
        raw=False,
    ).fillna(0.0)
    df["autocorr"] = autocorr

    # Gap detection
    gap_pct = ((open_ - prev_close) / prev_close.replace(0, np.nan)).fillna(0.0)

    # Classification
    regimes: List[str] = []
    for i in range(len(df)):
        row = df.iloc[i]

        # Gap day override
        if abs(gap_pct.iloc[i]) >= 0.005:
            regimes.append(Regime.GAP_DAY.value)
            continue

        # Breakout: large bar + volume expansion
        bar_range = float(row["high"]) - float(row["low"])
        if (
            bar_range > breakout_atr_mult * float(row["atr"])
            and volume_expansion.iloc[i]
        ):
            regimes.append(Regime.BREAKOUT.value)
            continue

        # High / low volatility
        if row["vol_regime"] == "HIGH":
            if abs(row["ema_fast"] - row["ema_slow"]) / max(row["ema_slow"], 1e-6) > 0.0025:
                if row["ema_fast"] > row["ema_slow"]:
                    regimes.append(Regime.TRENDING_BULLISH.value)
                else:
                    regimes.append(Regime.TRENDING_BEARISH.value)
            else:
                regimes.append(Regime.HIGH_VOLATILITY.value)
            continue

        if row["vol_regime"] == "LOW":
            regimes.append(Regime.LOW_VOLATILITY.value)
            continue

        # Trending / ranging based on EMA spread and ADX
        is_trending = (
            abs(row["ema_fast"] - row["ema_slow"]) / max(row["ema_slow"], 1e-6) > 0.0025
            or row["adx_proxy"] > adx_threshold
        )

        if is_trending:
            if row["ema_fast"] > row["ema_slow"]:
                regimes.append(Regime.TRENDING_BULLISH.value)
            else:
                regimes.append(Regime.TRENDING_BEARISH.value)
        else:
            if row["atr"] > df["atr"].rolling(atr_period * 2).mean().iloc[i]:
                regimes.append(Regime.VOLATILE_RANGING.value)
            else:
                regimes.append(Regime.QUIET_RANGING.value)

    df["regime"] = regimes
    return df


def regime_distribution(df: pd.DataFrame) -> Dict[str, float]:
    """Return % distribution of regimes in a classified DataFrame."""
    counts = df["regime"].value_counts()
    total = len(df)
    return {k: round(v / total * 100, 2) for k, v in counts.items()}


def current_regime(df: pd.DataFrame) -> str:
    """Return the most recent regime label from a classified DataFrame."""
    if "regime" not in df.columns:
        raise ValueError("DataFrame must have a 'regime' column. Run classify_regimes first.")
    return str(df["regime"].iloc[-1])
