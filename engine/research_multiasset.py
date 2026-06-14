"""
Multi-asset research analytics.

Provides:
- Correlation matrix & rolling correlation
- Sector heatmap data
- Pair discovery (top correlated / anti-correlated pairs)
- Cointegration testing (Engle-Granger)
- Spread analysis & half-life estimation (Ornstein-Uhlenbeck)
- Z-score monitoring
- Lead-lag detection (cross-correlation)
- Sector breadth calculations
- Cross-sectional factor ranking
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------


def correlation_matrix(
    prices: pd.DataFrame,
    method: str = "pearson",
    log_returns: bool = True,
) -> pd.DataFrame:
    """
    Compute the pairwise correlation matrix from a wide price DataFrame.

    Parameters
    ----------
    prices : DataFrame  shape (T x N)
    method : 'pearson' | 'spearman' | 'kendall'
    log_returns : if True convert prices to log-returns first

    Returns
    -------
    DataFrame  shape (N x N)
    """
    if log_returns:
        data = np.log(prices / prices.shift(1)).dropna()
    else:
        data = prices.pct_change().dropna()
    return data.corr(method=method)


def rolling_correlation(
    prices: pd.DataFrame,
    sym1: str,
    sym2: str,
    window: int = 20,
    log_returns: bool = True,
) -> pd.Series:
    """Rolling pairwise correlation between sym1 and sym2."""
    if log_returns:
        rets = np.log(prices / prices.shift(1)).dropna()
    else:
        rets = prices.pct_change().dropna()
    if sym1 not in rets.columns or sym2 not in rets.columns:
        return pd.Series(dtype=float)
    return rets[sym1].rolling(window).corr(rets[sym2])


def sector_heatmap_data(
    prices: pd.DataFrame,
    groups: Dict[str, List[str]],
    window: int = 60,
) -> Dict[str, Any]:
    """
    Compute average intra-sector correlation for each group over a rolling window.
    Returns data ready for heatmap visualisation.
    """
    corr = correlation_matrix(prices.iloc[-window:])
    result: Dict[str, Any] = {}
    for group, symbols in groups.items():
        valid = [s for s in symbols if s in corr.columns]
        if len(valid) < 2:
            result[group] = {"avg_corr": None, "symbols": valid, "matrix": {}}
            continue
        sub = corr.loc[valid, valid]
        mask = np.triu(np.ones(sub.shape, dtype=bool), k=1)
        vals = sub.values[mask]
        result[group] = {
            "avg_corr": float(np.nanmean(vals)),
            "symbols": valid,
            "matrix": sub.round(4).to_dict(),
        }
    return result


# ---------------------------------------------------------------------------
# Pair discovery
# ---------------------------------------------------------------------------


def discover_pairs(
    prices: pd.DataFrame,
    top_n: int = 10,
    log_returns: bool = True,
    min_corr: float = 0.6,
) -> List[Dict[str, Any]]:
    """
    Find top correlated and anti-correlated symbol pairs.

    Returns
    -------
    list of dicts sorted by |correlation| descending
    """
    corr = correlation_matrix(prices, log_returns=log_returns)
    symbols = corr.columns.tolist()
    pairs: List[Dict[str, Any]] = []
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            c = corr.iloc[i, j]
            if np.isnan(c):
                continue
            if abs(c) >= min_corr:
                pairs.append(
                    {
                        "sym1": symbols[i],
                        "sym2": symbols[j],
                        "correlation": round(float(c), 4),
                        "pair_type": "correlated" if c > 0 else "anti_correlated",
                    }
                )
    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return pairs[:top_n]


# ---------------------------------------------------------------------------
# Cointegration (Engle-Granger)
# ---------------------------------------------------------------------------


def cointegration_test(
    series1: pd.Series,
    series2: pd.Series,
    significance: float = 0.05,
) -> Dict[str, Any]:
    """
    Engle-Granger two-step cointegration test.
    Falls back to a simple OLS residual ADF if statsmodels is unavailable.

    Returns
    -------
    dict with keys: cointegrated, pvalue, hedge_ratio, intercept, adf_stat
    """
    # Align
    df = pd.DataFrame({"y": series1, "x": series2}).dropna()
    if len(df) < 30:
        return {"cointegrated": False, "pvalue": 1.0, "adf_stat": None, "hedge_ratio": None, "intercept": None, "error": "insufficient data"}

    y, x = df["y"].values, df["x"].values

    # OLS regression y = alpha + beta * x + residual
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    intercept, hedge_ratio = float(beta[0]), float(beta[1])
    residuals = y - (intercept + hedge_ratio * x)

    # ADF test on residuals
    try:
        from statsmodels.tsa.stattools import adfuller  # type: ignore

        adf_res = adfuller(residuals, autolag="AIC")
        adf_stat = float(adf_res[0])
        pvalue = float(adf_res[1])
    except ImportError:
        # Naive ADF approximation: test if first-differenced residuals are stationary
        diff = np.diff(residuals)
        corr_r = np.corrcoef(residuals[:-1], diff)[0, 1]
        pvalue = 0.01 if corr_r < -0.5 else 0.5
        adf_stat = corr_r

    return {
        "cointegrated": pvalue < significance,
        "pvalue": round(pvalue, 6),
        "adf_stat": round(adf_stat, 4),
        "hedge_ratio": round(hedge_ratio, 4),
        "intercept": round(intercept, 4),
        "significance": significance,
    }


# ---------------------------------------------------------------------------
# Spread analysis, half-life, z-score
# ---------------------------------------------------------------------------


def compute_spread(
    series1: pd.Series,
    series2: pd.Series,
    hedge_ratio: float = 1.0,
    log_spread: bool = False,
) -> pd.Series:
    """Compute price spread or log-price spread."""
    if log_spread:
        return np.log(series1) - hedge_ratio * np.log(series2)
    return series1 - hedge_ratio * series2


def half_life(spread: pd.Series) -> float:
    """
    Estimate the Ornstein-Uhlenbeck half-life of mean reversion.
    Uses the OLS regression: Δspread(t) = alpha + beta * spread(t-1).
    Half-life = -ln(2) / beta.
    """
    s = spread.dropna()
    if len(s) < 10:
        return float("nan")
    delta = s.diff().dropna()
    lag = s.shift(1).dropna()
    # Align
    n = min(len(delta), len(lag))
    delta, lag = delta.iloc[-n:].values, lag.iloc[-n:].values
    X = np.column_stack([np.ones(len(lag)), lag])
    beta = np.linalg.lstsq(X, delta, rcond=None)[0]
    b = float(beta[1])
    if b >= 0:
        return float("inf")  # non-mean-reverting
    return float(-np.log(2) / b)


def z_score_series(spread: pd.Series, window: int = 20) -> pd.Series:
    """Rolling z-score of spread."""
    mu = spread.rolling(window).mean()
    sigma = spread.rolling(window).std()
    return (spread - mu) / sigma.replace(0, np.nan)


# ---------------------------------------------------------------------------
# Lead-lag detection
# ---------------------------------------------------------------------------


def lead_lag_detection(
    prices: pd.DataFrame,
    max_lag: int = 5,
    log_returns: bool = True,
) -> Dict[str, Any]:
    """
    For every pair compute cross-correlation at lags -max_lag..+max_lag.
    Positive lag means sym1 leads sym2.

    Returns
    -------
    dict: pairs -> {lag, max_xcorr, relationship}
    """
    if log_returns:
        rets = np.log(prices / prices.shift(1)).dropna()
    else:
        rets = prices.pct_change().dropna()

    symbols = rets.columns.tolist()
    results: Dict[str, Any] = {}

    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            s1 = symbols[i]
            s2 = symbols[j]
            r1 = rets[s1].values
            r2 = rets[s2].values

            best_lag, best_corr = 0, 0.0
            for lag in range(-max_lag, max_lag + 1):
                if lag == 0:
                    c = float(np.corrcoef(r1, r2)[0, 1])
                elif lag > 0:
                    c = float(np.corrcoef(r1[lag:], r2[:-lag])[0, 1])
                else:
                    c = float(np.corrcoef(r1[:lag], r2[-lag:])[0, 1])
                if abs(c) > abs(best_corr):
                    best_corr = c
                    best_lag = lag

            key = f"{s1}/{s2}"
            if best_lag > 0:
                relationship = f"{s1} leads {s2} by {best_lag} bars"
            elif best_lag < 0:
                relationship = f"{s2} leads {s1} by {abs(best_lag)} bars"
            else:
                relationship = "Simultaneous"

            results[key] = {
                "sym1": s1,
                "sym2": s2,
                "best_lag": best_lag,
                "max_xcorr": round(best_corr, 4),
                "relationship": relationship,
            }

    return results


# ---------------------------------------------------------------------------
# Sector breadth
# ---------------------------------------------------------------------------


def sector_breadth(
    prices: pd.DataFrame,
    window: int = 20,
) -> Dict[str, Any]:
    """
    For each symbol, compute whether it is above its rolling mean (breadth).
    Returns overall breadth percentage and per-symbol indicator.
    """
    rets = prices.pct_change().dropna()
    above_mean: Dict[str, bool] = {}
    for col in prices.columns:
        s = prices[col].dropna()
        if len(s) >= window:
            above_mean[col] = bool(s.iloc[-1] > s.rolling(window).mean().iloc[-1])

    breadth_pct = (
        sum(above_mean.values()) / len(above_mean) * 100 if above_mean else 0.0
    )

    # Cumulative advance/decline
    adv = sum(1 for v in above_mean.values() if v)
    dec = len(above_mean) - adv

    return {
        "breadth_pct": round(breadth_pct, 2),
        "advancing": adv,
        "declining": dec,
        "per_symbol": above_mean,
        "ad_ratio": None if dec == 0 else round(adv / dec, 2),
    }


# ---------------------------------------------------------------------------
# Cross-sectional ranking
# ---------------------------------------------------------------------------


def cross_sectional_ranking(
    prices: pd.DataFrame,
    factor: str = "momentum",
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Rank symbols cross-sectionally on a chosen factor.

    Factors:
    - momentum    : return over `lookback` bars
    - volatility  : annualised vol over `lookback` bars (lower = better rank)
    - sharpe      : momentum / volatility

    Returns
    -------
    DataFrame with columns: symbol, raw_score, rank, percentile
    """
    scores: Dict[str, float] = {}
    rets = prices.pct_change().dropna()

    for sym in prices.columns:
        if len(prices[sym].dropna()) < lookback:
            continue
        r = rets[sym].iloc[-lookback:]
        if factor == "momentum":
            scores[sym] = float(r.sum())
        elif factor == "volatility":
            scores[sym] = -float(r.std() * np.sqrt(252))  # negate: lower vol = better
        elif factor == "sharpe":
            mu, sigma = float(r.mean()), float(r.std())
            scores[sym] = float(mu / sigma) if sigma > 0 else 0.0
        else:
            scores[sym] = float(r.sum())

    if not scores:
        return pd.DataFrame(columns=["symbol", "raw_score", "rank", "percentile"])

    df = pd.DataFrame(
        [{"symbol": k, "raw_score": v} for k, v in scores.items()]
    )
    df["rank"] = df["raw_score"].rank(ascending=False).astype(int)
    df["percentile"] = (
        (len(df) - df["rank"]) / (len(df) - 1) * 100
    ).round(1)
    df = df.sort_values("rank").reset_index(drop=True)
    df["raw_score"] = df["raw_score"].round(5)
    return df
