"""
Additional Research Modules.

Provides:
- Seasonality analysis (day-of-week, month-of-year)
- Intraday time-of-day effects
- Volume profile (POC, VAH, VAL)
- Support & Resistance detection
- Market breadth indicators
- Sector rotation analysis
- Cross-sectional factor ranking (extended)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Seasonality
# ---------------------------------------------------------------------------

def seasonality_analysis(df: pd.DataFrame, time_col: str = "time") -> Dict[str, Any]:
    """
    Compute day-of-week and month-of-year return patterns.

    Returns mean return % and win rate for each day/month bucket.
    """
    df = df.copy()
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col]).sort_values(time_col)
        df["_dt"] = df[time_col]
    elif isinstance(df.index, pd.DatetimeIndex):
        df["_dt"] = df.index
    else:
        return {"error": "No parseable datetime column"}

    df["_ret"] = df["close"].astype(float).pct_change().fillna(0.0) * 100
    df["_dow"] = df["_dt"].dt.day_name()
    df["_month"] = df["_dt"].dt.month_name()
    df["_hour"] = df["_dt"].dt.hour

    def _bucket_stats(series_groups) -> List[Dict]:
        result = []
        for name, grp in series_groups:
            rets = grp["_ret"].values
            result.append({
                "bucket": name,
                "mean_return_pct": round(float(np.mean(rets)), 4),
                "median_return_pct": round(float(np.median(rets)), 4),
                "win_rate": round(float(np.mean(rets > 0)), 4),
                "count": int(len(rets)),
                "std": round(float(np.std(rets)), 4),
            })
        return result

    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    dow_data = {r["bucket"]: r for r in _bucket_stats(df.groupby("_dow"))}
    dow_ordered = [dow_data[d] for d in dow_order if d in dow_data]

    month_order = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    month_data = {r["bucket"]: r for r in _bucket_stats(df.groupby("_month"))}
    month_ordered = [month_data[m] for m in month_order if m in month_data]

    best_dow = max(dow_ordered, key=lambda x: x["mean_return_pct"])["bucket"] if dow_ordered else None
    worst_dow = min(dow_ordered, key=lambda x: x["mean_return_pct"])["bucket"] if dow_ordered else None

    return {
        "day_of_week": dow_ordered,
        "month_of_year": month_ordered,
        "best_day": best_dow,
        "worst_day": worst_dow,
    }


# ---------------------------------------------------------------------------
# Intraday time-of-day effects
# ---------------------------------------------------------------------------

def intraday_tod_effects(df: pd.DataFrame, time_col: str = "time") -> Dict[str, Any]:
    """
    Compute average returns, volume, and volatility by hour of day.
    Only meaningful for intraday data.
    """
    df = df.copy()
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col]).sort_values(time_col)
        df["_hour"] = df[time_col].dt.hour
    else:
        return {"error": "No time column found"}

    df["_ret"] = df["close"].astype(float).pct_change().fillna(0.0) * 100
    df["_vol"] = df["volume"].astype(float) if "volume" in df.columns else 1.0

    hourly = df.groupby("_hour").agg(
        mean_return=("_ret", "mean"),
        std_return=("_ret", "std"),
        mean_volume=("_vol", "mean"),
        count=("_ret", "count"),
    ).reset_index()

    hourly_list = [
        {
            "hour": int(row["_hour"]),
            "mean_return_pct": round(float(row["mean_return"]), 4),
            "std_pct": round(float(row["std_return"]), 4),
            "mean_volume": round(float(row["mean_volume"]), 0),
            "count": int(row["count"]),
        }
        for _, row in hourly.iterrows()
    ]

    best_hour = max(hourly_list, key=lambda x: x["mean_return_pct"])["hour"] if hourly_list else None
    worst_hour = min(hourly_list, key=lambda x: x["mean_return_pct"])["hour"] if hourly_list else None

    return {
        "hourly": hourly_list,
        "best_hour": best_hour,
        "worst_hour": worst_hour,
    }


# ---------------------------------------------------------------------------
# Volume Profile
# ---------------------------------------------------------------------------

def volume_profile(
    df: pd.DataFrame,
    bins: int = 30,
    value_area_pct: float = 0.70,
) -> Dict[str, Any]:
    """
    Compute a simplified Volume Profile.

    Returns:
    - poc_price   : Point of Control (price with highest volume)
    - vah_price   : Value Area High
    - val_price   : Value Area Low
    - profile     : list of {price_level, volume}
    """
    df = df.copy()
    close = df["close"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

    price_min, price_max = float(close.min()), float(close.max())
    if price_min == price_max:
        return {"error": "No price variation"}

    edges = np.linspace(price_min, price_max, bins + 1)
    bin_centers = (edges[:-1] + edges[1:]) / 2

    vol_profile = np.zeros(bins)
    for c, v in zip(close.values, volume.values):
        idx = int(np.clip(np.searchsorted(edges, c) - 1, 0, bins - 1))
        vol_profile[idx] += v

    poc_idx = int(np.argmax(vol_profile))
    poc_price = float(bin_centers[poc_idx])

    # Value area: accumulate from POC until >= 70% of volume
    total_vol = float(vol_profile.sum())
    target = total_vol * value_area_pct
    accumulated = float(vol_profile[poc_idx])
    lo, hi = poc_idx, poc_idx

    while accumulated < target and (lo > 0 or hi < bins - 1):
        below = vol_profile[lo - 1] if lo > 0 else 0.0
        above = vol_profile[hi + 1] if hi < bins - 1 else 0.0
        if above >= below and hi < bins - 1:
            hi += 1
            accumulated += vol_profile[hi]
        elif lo > 0:
            lo -= 1
            accumulated += vol_profile[lo]
        else:
            hi += 1
            accumulated += vol_profile[hi]

    return {
        "poc_price": round(poc_price, 2),
        "vah_price": round(float(bin_centers[hi]), 2),
        "val_price": round(float(bin_centers[lo]), 2),
        "value_area_pct": value_area_pct,
        "profile": [
            {"price_level": round(float(bin_centers[i]), 2), "volume": round(float(vol_profile[i]), 0)}
            for i in range(bins)
        ],
    }


# ---------------------------------------------------------------------------
# Support & Resistance
# ---------------------------------------------------------------------------

def detect_support_resistance(
    df: pd.DataFrame,
    window: int = 10,
    min_touches: int = 2,
    tolerance_pct: float = 0.5,
) -> Dict[str, Any]:
    """
    Detect significant support and resistance levels using local extrema.

    Returns levels with touch count and classification.
    """
    close = df["close"].astype(float).reset_index(drop=True)
    high = df["high"].astype(float).reset_index(drop=True) if "high" in df.columns else close
    low = df["low"].astype(float).reset_index(drop=True) if "low" in df.columns else close

    # Local highs and lows
    resistance_prices: List[float] = []
    support_prices: List[float] = []

    for i in range(window, len(close) - window):
        h_window = high.iloc[i - window : i + window + 1]
        l_window = low.iloc[i - window : i + window + 1]

        if float(high.iloc[i]) == float(h_window.max()):
            resistance_prices.append(float(high.iloc[i]))
        if float(low.iloc[i]) == float(l_window.min()):
            support_prices.append(float(low.iloc[i]))

    def _cluster(prices: List[float]) -> List[Dict]:
        if not prices:
            return []
        prices_s = sorted(prices)
        clusters: List[Dict] = []
        current_cluster = [prices_s[0]]
        for p in prices_s[1:]:
            base = current_cluster[0]
            if abs(p - base) / base * 100 <= tolerance_pct:
                current_cluster.append(p)
            else:
                clusters.append({
                    "price": round(float(np.mean(current_cluster)), 2),
                    "touches": len(current_cluster),
                })
                current_cluster = [p]
        clusters.append({
            "price": round(float(np.mean(current_cluster)), 2),
            "touches": len(current_cluster),
        })
        return [c for c in clusters if c["touches"] >= min_touches]

    resistance = sorted(_cluster(resistance_prices), key=lambda x: x["price"])
    support = sorted(_cluster(support_prices), key=lambda x: x["price"])
    current_price = float(close.iloc[-1])

    return {
        "resistance_levels": resistance,
        "support_levels": support,
        "current_price": round(current_price, 2),
        "nearest_resistance": min(
            [r for r in resistance if r["price"] > current_price],
            key=lambda x: x["price"] - current_price,
            default=None,
        ),
        "nearest_support": max(
            [s for s in support if s["price"] < current_price],
            key=lambda x: x["price"],
            default=None,
        ),
    }


# ---------------------------------------------------------------------------
# Market Breadth Indicators
# ---------------------------------------------------------------------------

def market_breadth_indicators(
    prices: pd.DataFrame,
    windows: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Compute advance/decline ratios and breadth oscillator across multiple windows.
    """
    windows = windows or [5, 20, 50]
    result: Dict[str, Any] = {"per_window": {}}

    rets = prices.pct_change().dropna()
    daily_rets = rets.iloc[-1]  # latest bar returns

    adv = int((daily_rets > 0).sum())
    dec = int((daily_rets < 0).sum())
    unch = int((daily_rets == 0).sum())

    result["advance"] = adv
    result["decline"] = dec
    result["unchanged"] = unch
    result["ad_line"] = adv - dec
    result["ad_ratio"] = round(adv / max(dec, 1), 2)

    for w in windows:
        window_rets = rets.iloc[-w:]
        above_ema = {}
        for sym in prices.columns:
            s = prices[sym].dropna()
            if len(s) >= w:
                ema = float(s.ewm(span=w, adjust=False).mean().iloc[-1])
                above_ema[sym] = bool(float(s.iloc[-1]) > ema)
        pct_above = sum(above_ema.values()) / max(len(above_ema), 1) * 100
        result["per_window"][f"pct_above_ema{w}"] = round(pct_above, 2)

    return result


# ---------------------------------------------------------------------------
# Sector Rotation Analysis
# ---------------------------------------------------------------------------

def sector_rotation_analysis(
    prices: pd.DataFrame,
    groups: Dict[str, List[str]],
    momentum_window: int = 20,
) -> Dict[str, Any]:
    """
    Compute average momentum for each sector group and rank them.

    Returns a leaderboard of sectors by recent momentum.
    """
    rets = prices.pct_change().dropna()
    sector_scores: List[Dict] = []

    for sector, symbols in groups.items():
        valid = [s for s in symbols if s in rets.columns]
        if not valid:
            continue
        recent = rets[valid].iloc[-momentum_window:]
        total_rets = (recent + 1).prod() - 1  # compound returns
        avg_mom = float(total_rets.mean())
        sector_scores.append({
            "sector": sector,
            "avg_momentum": round(avg_mom * 100, 2),
            "symbols": valid,
            "leaders": recent[valid].iloc[-1].nlargest(2).index.tolist(),
        })

    sector_scores.sort(key=lambda x: x["avg_momentum"], reverse=True)
    for i, s in enumerate(sector_scores):
        s["rank"] = i + 1

    return {
        "sectors": sector_scores,
        "leading_sector": sector_scores[0]["sector"] if sector_scores else None,
        "lagging_sector": sector_scores[-1]["sector"] if sector_scores else None,
    }
