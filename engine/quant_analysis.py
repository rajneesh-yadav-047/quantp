"""
Quantitative Analysis Engine — comprehensive statistical and quantitative
modules for strategy research, regime detection, and signal generation.

Modules:
- Mean Reversion Analysis (Hurst, Half-Life, OU Speed)
- Advanced Regime Detection (HMM, rolling, transitions)
- Volume Profile & Market Profile (POC, VAH, VAL, HVN, LVN)
- Gap Analysis
- Intraday Behavior Analysis
- Trend Persistence Analysis
- Volatility Structure Analysis
- Tail Risk Analysis
- Order Flow Proxies
- Multi-Timeframe Analysis
- Factor Exposure Analysis
- Feature Importance Engine
- Walk-Forward Stability Analysis
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")


# ============================================================================
# 1. Mean Reversion Analysis
# ============================================================================

def hurst_exponent(prices: pd.Series, max_lag: int = 100) -> Dict[str, Any]:
    """
    Estimate the Hurst exponent using R/S analysis.
    H < 0.5: mean-reverting
    H = 0.5: random walk
    H > 0.5: trending
    """
    s = prices.dropna().astype(float).values
    if len(s) < 50:
        return {"hurst": None, "interpretation": "insufficient data", "confidence": 0}

    n = len(s)
    lags = np.unique(np.logspace(1, np.log10(min(n // 4, max_lag)), 20).astype(int))
    lags = lags[lags >= 10]
    if len(lags) < 3:
        lags = np.array([10, 20, 30])

    log_tau = np.log(lags)
    log_rs = np.empty(len(lags))

    for idx, lag in enumerate(lags):
        chunks = n // lag
        if chunks < 1:
            log_rs[idx] = np.nan
            continue
        # Reshape into (chunks, lag) and compute R/S vectorized
        data = s[: chunks * lag].reshape(chunks, lag)
        means = data.mean(axis=1, keepdims=True)
        devs = data - means
        cum_devs = np.cumsum(devs, axis=1)
        r_vals = cum_devs.max(axis=1) - cum_devs.min(axis=1)
        s_vals = data.std(axis=1, ddof=0)
        rs = r_vals / np.where(s_vals > 0, s_vals, np.nan)
        log_rs[idx] = np.log(np.nanmean(rs))

    valid = ~np.isnan(log_rs)
    if valid.sum() < 3:
        return {"hurst": None, "interpretation": "insufficient data", "confidence": 0}

    log_tau = log_tau[valid]
    log_rs = log_rs[valid]

    slope, intercept, r_value, p_value, std_err = stats.linregress(log_tau, log_rs)
    hurst = float(slope)
    r_squared = r_value ** 2
    confidence = int(min(100, r_squared * 100 + (1 - min(p_value, 1)) * 50))

    if hurst < 0.45:
        interpretation = "mean_reverting"
    elif hurst < 0.55:
        interpretation = "random_walk"
    else:
        interpretation = "trending"

    return {
        "hurst": round(hurst, 4),
        "r_squared": round(r_squared, 4),
        "p_value": round(float(p_value), 6),
        "confidence": confidence,
        "interpretation": interpretation,
    }


def ornstein_uhlenbeck_params(series: pd.Series) -> Dict[str, Any]:
    """
    Fit an Ornstein-Uhlenbeck process to the series:
        dX(t) = theta * (mu - X(t)) * dt + sigma * dW(t)
    Returns theta, mu, sigma, and half-life.
    """
    s = series.dropna().astype(float)
    if len(s) < 30:
        return {"theta": None, "mu": None, "sigma": None, "half_life": None, "mean_reversion_speed": None}

    X_lag = s.shift(1).dropna()
    X = s.iloc[1:]
    X_lag, X = X_lag.align(X, join="inner")

    X_lag_vals = X_lag.values.reshape(-1, 1)
    X_vals = X.values

    model = LinearRegression()
    model.fit(X_lag_vals, X_vals)
    b = model.coef_[0]
    a = model.intercept_

    theta = -np.log(b) if b > 0 else 0.0
    mu = a / (1 - b) if b != 1 else np.mean(s)
    residuals = X_vals - (a + b * X_lag_vals.flatten())
    sigma = float(np.std(residuals))

    half_life = float(-np.log(2) / np.log(b)) if b > 0 and b < 1 else float("inf")

    return {
        "theta": round(theta, 6),
        "mu": round(float(mu), 4),
        "sigma": round(sigma, 6),
        "half_life_bars": round(half_life, 2) if np.isfinite(half_life) else None,
        "mean_reversion_speed": round(theta, 4) if np.isfinite(theta) else 0.0,
    }


def mean_reversion_analysis(prices: pd.Series) -> Dict[str, Any]:
    """
    Comprehensive mean reversion analysis combining Hurst, OU, and half-life.
    """
    hurst = hurst_exponent(prices)
    ou = ornstein_uhlenbeck_params(prices)

    score = 0
    if hurst.get("hurst") is not None and hurst["hurst"] < 0.5:
        score += 30 + int((0.5 - hurst["hurst"]) * 100)
    hl = ou.get("half_life_bars")
    if hl is not None and np.isfinite(hl):
        if 5 <= hl <= 50:
            score += 30
        elif hl < 5:
            score += 15
        elif hl <= 100:
            score += 10
    if ou.get("theta") is not None and ou["theta"] > 0.01:
        score += 20

    score = min(100, score)

    return {
        "hurst": hurst.get("hurst"),
        "half_life_bars": ou.get("half_life_bars"),
        "mean_reversion_speed": ou.get("mean_reversion_speed"),
        "mean_reversion_strength": score,
        "ou_params": ou,
        "hurst_detail": hurst,
    }


# ============================================================================
# 2. Advanced Regime Detection
# ============================================================================

def hmm_regimes(df: pd.DataFrame, n_states: int = 3) -> Dict[str, Any]:
    """
    Hidden Markov Model regime detection using returns and volatility as features.
    Falls back to k-means if hmmlearn is not available.
    """
    df = df.copy()
    returns = df["close"].pct_change().fillna(0).astype(float)
    vol = returns.rolling(20).std().fillna(0).astype(float)
    features = pd.DataFrame({"ret": returns, "vol": vol}).dropna()

    if len(features) < 60:
        return {"error": "insufficient data for HMM", "current_regime": None}

    try:
        from hmmlearn.hmm import GaussianHMM

        model = GaussianHMM(n_components=n_states, covariance_type="diag", n_iter=200, random_state=42)
        model.fit(features.values)
        hidden_states = model.predict(features.values)

        state_labels = {}
        for state in range(n_states):
            mask = hidden_states == state
            avg_ret = float(np.mean(features["ret"][mask]))
            avg_vol = float(np.mean(features["vol"][mask]))
            if avg_ret > 0.001 and avg_vol > 0.01:
                state_labels[state] = "TRENDING_BULLISH"
            elif avg_ret < -0.001 and avg_vol > 0.01:
                state_labels[state] = "TRENDING_BEARISH"
            elif avg_vol > 0.015:
                state_labels[state] = "VOLATILE_RANGING"
            else:
                state_labels[state] = "QUIET_RANGING"

        trans_mat = model.transmat_
        transition_probs = {}
        for i in range(n_states):
            state_name = state_labels[i]
            transition_probs[state_name] = {
                state_labels[j]: round(float(trans_mat[i, j]) * 100, 1)
                for j in range(n_states)
            }

        current_state = int(hidden_states[-1])
        current_regime = state_labels[current_state]
        current_probs = trans_mat[current_state]
        confidence = int(np.max(current_probs) * 100)

        prob_next = {
            state_labels[j]: round(float(current_probs[j]) * 100, 1)
            for j in range(n_states)
        }

        return {
            "current_regime": current_regime,
            "confidence": confidence,
            "prob_next_regime": prob_next,
            "transition_matrix": transition_probs,
            "state_labels": state_labels,
            "hidden_states": hidden_states.tolist(),
        }
    except ImportError:
        from sklearn.cluster import KMeans

        kmeans = KMeans(n_clusters=n_states, random_state=42, n_init=10)
        hidden_states = kmeans.fit_predict(features.values)

        state_labels = {}
        for state in range(n_states):
            mask = hidden_states == state
            avg_ret = float(np.mean(features["ret"][mask]))
            avg_vol = float(np.mean(features["vol"][mask]))
            if avg_ret > 0.001 and avg_vol > 0.01:
                state_labels[state] = "TRENDING_BULLISH"
            elif avg_ret < -0.001 and avg_vol > 0.01:
                state_labels[state] = "TRENDING_BEARISH"
            elif avg_vol > 0.015:
                state_labels[state] = "VOLATILE_RANGING"
            else:
                state_labels[state] = "QUIET_RANGING"

        current_state = int(hidden_states[-1])
        current_regime = state_labels[current_state]

        return {
            "current_regime": current_regime,
            "confidence": 60,
            "prob_next_regime": {},
            "transition_matrix": {},
            "state_labels": state_labels,
            "hidden_states": hidden_states.tolist(),
            "method": "kmeans_fallback",
        }


def rolling_regime_detection(df: pd.DataFrame, window: int = 60) -> Dict[str, Any]:
    """
    Rolling regime detection that tracks regime changes over time.
    """
    df = df.copy()
    returns = df["close"].pct_change().fillna(0).astype(float)
    vol = returns.rolling(20).std().fillna(0).astype(float)
    features = pd.DataFrame({"ret": returns, "vol": vol}).dropna()

    if len(features) < window * 2:
        return {"error": "insufficient data"}

    regimes = []
    for i in range(window, len(features)):
        window_data = features.iloc[i - window : i]
        avg_ret = float(window_data["ret"].mean())
        avg_vol = float(window_data["vol"].mean())
        if avg_ret > 0.001 and avg_vol > 0.01:
            regimes.append("TRENDING_BULLISH")
        elif avg_ret < -0.001 and avg_vol > 0.01:
            regimes.append("TRENDING_BEARISH")
        elif avg_vol > 0.015:
            regimes.append("VOLATILE_RANGING")
        else:
            regimes.append("QUIET_RANGING")

    transitions = defaultdict(lambda: defaultdict(int))
    for i in range(len(regimes) - 1):
        transitions[regimes[i]][regimes[i + 1]] += 1

    transition_probs = {}
    for from_regime, to_counts in transitions.items():
        total = sum(to_counts.values())
        if total > 0:
            transition_probs[from_regime] = {
                to_regime: round(count / total * 100, 1)
                for to_regime, count in to_counts.items()
            }

    regime_counts = pd.Series(regimes).value_counts().to_dict()
    total = len(regimes)
    regime_pct = {k: round(v / total * 100, 1) for k, v in regime_counts.items()}

    return {
        "current_regime": regimes[-1] if regimes else None,
        "regime_history": regimes[-100:] if len(regimes) > 100 else regimes,
        "regime_distribution": regime_pct,
        "transition_probabilities": transition_probs,
    }


# ============================================================================
# 3. Volume Profile & Market Profile (enhanced)
# ============================================================================

def volume_profile_enhanced(
    df: pd.DataFrame,
    bins: int = 50,
    value_area_pct: float = 0.70,
) -> Dict[str, Any]:
    """
    Enhanced Volume Profile with HVN and LVN detection.
    """
    df = df.copy()
    close = df["close"].astype(float).values
    volume = df["volume"].astype(float).values if "volume" in df.columns else np.ones(len(df))

    price_min, price_max = float(close.min()), float(close.max())
    if price_min == price_max:
        return {"error": "No price variation"}

    edges = np.linspace(price_min, price_max, bins + 1)
    bin_centers = (edges[:-1] + edges[1:]) / 2

    # Vectorized digitization using np.searchsorted
    idx = np.clip(np.searchsorted(edges, close) - 1, 0, bins - 1)
    vol_profile = np.bincount(idx, weights=volume, minlength=bins).astype(float)

    poc_idx = int(np.argmax(vol_profile))
    poc_price = float(bin_centers[poc_idx])

    # Value area
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

    # HVN / LVN using percentile thresholds
    nonzero = vol_profile[vol_profile > 0]
    if len(nonzero) > 0:
        vol_threshold = np.percentile(nonzero, 80)
        lvn_threshold = np.percentile(nonzero, 20)
    else:
        vol_threshold = 0
        lvn_threshold = 0

    hvn = [
        {"price": round(float(bin_centers[i]), 2), "volume": round(float(vol_profile[i]), 0)}
        for i in range(bins)
        if vol_profile[i] >= vol_threshold and vol_profile[i] > 0
    ]
    hvn = sorted(hvn, key=lambda x: x["volume"], reverse=True)[:5]

    lvn = [
        {"price": round(float(bin_centers[i]), 2), "volume": round(float(vol_profile[i]), 0)}
        for i in range(bins)
        if vol_profile[i] <= lvn_threshold and vol_profile[i] > 0
    ]
    lvn = sorted(lvn, key=lambda x: x["volume"])[:5]

    return {
        "POC": round(poc_price, 2),
        "VAH": round(float(bin_centers[hi]), 2),
        "VAL": round(float(bin_centers[lo]), 2),
        "value_area_pct": value_area_pct,
        "HVN": hvn,
        "LVN": lvn,
        "profile": [
            {"price_level": round(float(bin_centers[i]), 2), "volume": round(float(vol_profile[i]), 0)}
            for i in range(bins)
        ],
    }


# ============================================================================
# 4. Gap Analysis
# ============================================================================

def gap_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze gap-up, gap-down, fill probability, and fill time.
    Vectorized for speed.
    """
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.sort_values("time").reset_index(drop=True)

    close = df["close"].astype(float).values
    open_ = df["open"].astype(float).values
    high = df["high"].astype(float).values
    low = df["low"].astype(float).values

    prev_close = np.empty_like(close)
    prev_close[0] = np.nan
    prev_close[1:] = close[:-1]

    gap = open_ - prev_close
    gap_pct = np.where(prev_close != 0, gap / prev_close * 100, 0)
    gap_pct[0] = 0

    gap_up_mask = gap_pct > 0
    gap_down_mask = gap_pct < 0

    gap_up_count = int(gap_up_mask.sum())
    gap_down_count = int(gap_down_mask.sum())
    total_gaps = gap_up_count + gap_down_count

    if total_gaps == 0:
        return {
            "gap_up_freq": 0,
            "gap_down_freq": 0,
            "gap_fill_rate": None,
            "avg_fill_time_bars": None,
            "gap_continuation_prob": None,
            "gap_size_mean": None,
            "gap_size_median": None,
            "gap_size_p75": None,
            "gap_size_std": None,
        }

    # Gap size statistics for adaptive threshold
    abs_gap_pct = np.abs(gap_pct[1:])  # skip first bar which is always 0
    abs_gap_pct = abs_gap_pct[np.isfinite(abs_gap_pct)]
    gap_size_mean = round(float(np.mean(abs_gap_pct)), 3) if len(abs_gap_pct) > 0 else 0.0
    gap_size_median = round(float(np.median(abs_gap_pct)), 3) if len(abs_gap_pct) > 0 else 0.0
    gap_size_p75 = round(float(np.percentile(abs_gap_pct, 75)), 3) if len(abs_gap_pct) > 0 else 0.0
    gap_size_std = round(float(np.std(abs_gap_pct)), 3) if len(abs_gap_pct) > 0 else 0.0

    # Vectorized fill detection: for each gap, check if prev_close is crossed in next 20 bars
    fill_times = []
    filled_count = 0
    continuation_count = 0

    max_lookback = 20
    for i in range(1, len(df)):
        if gap_pct[i] == 0 or np.isnan(prev_close[i]):
            continue
        pc = prev_close[i]
        end = min(i + max_lookback + 1, len(df))
        # Check if filled within same bar
        if low[i] <= pc <= high[i]:
            fill_times.append(1)
            filled_count += 1
            continue
        # Check subsequent bars
        sub_low = low[i + 1 : end]
        sub_high = high[i + 1 : end]
        if len(sub_low) == 0:
            continuation_count += 1
            continue
        filled = (sub_low <= pc) & (pc <= sub_high)
        if filled.any():
            fill_bar = int(np.argmax(filled)) + 2  # +1 for next bar, +1 for same-bar offset
            fill_times.append(fill_bar)
            filled_count += 1
        else:
            continuation_count += 1

    fill_rate = round(filled_count / total_gaps * 100, 1) if total_gaps > 0 else 0
    avg_fill_time = round(float(np.mean(fill_times)), 1) if fill_times else None
    continuation_prob = round(continuation_count / total_gaps * 100, 1) if total_gaps > 0 else 0

    return {
        "gap_up_freq": round(gap_up_count / len(df) * 100, 1),
        "gap_down_freq": round(gap_down_count / len(df) * 100, 1),
        "gap_fill_rate": fill_rate,
        "avg_fill_time_bars": avg_fill_time,
        "gap_continuation_prob": continuation_prob,
        "total_gaps": total_gaps,
        "gap_size_mean": gap_size_mean,
        "gap_size_median": gap_size_median,
        "gap_size_p75": gap_size_p75,
        "gap_size_std": gap_size_std,
    }


# ============================================================================
# 5. Intraday Behavior Analysis
# ============================================================================

def intraday_behavior_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze volatility, range, win-rate, and volume by hour.
    """
    df = df.copy()
    if "time" not in df.columns:
        return {"error": "No time column"}

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)

    df["hour"] = df["time"].dt.hour
    df["ret"] = df["close"].pct_change().fillna(0) * 100
    df["range"] = (df["high"] - df["low"]) / df["close"] * 100
    df["vol"] = df["volume"] if "volume" in df.columns else 0

    hourly = df.groupby("hour").agg(
        mean_volatility=("ret", lambda x: float(x.std()) * 100 if len(x) > 1 else 0),
        mean_range=("range", "mean"),
        win_rate=("ret", lambda x: float(np.mean(x > 0)) * 100 if len(x) > 0 else 0),
        mean_volume=("vol", "mean"),
        count=("ret", "count"),
    ).reset_index()

    hourly_list = [
        {
            "hour": int(row["hour"]),
            "volatility": round(float(row["mean_volatility"]), 2),
            "range_pct": round(float(row["mean_range"]), 3),
            "win_rate": round(float(row["win_rate"]), 1),
            "volume": round(float(row["mean_volume"]), 0),
            "count": int(row["count"]),
        }
        for _, row in hourly.iterrows()
    ]

    best_score = -1
    best_window = None
    for i in range(len(hourly_list) - 1):
        h1, h2 = hourly_list[i], hourly_list[i + 1]
        if h1["count"] < 5 or h2["count"] < 5:
            continue
        score = h1["win_rate"] + h2["win_rate"] + (h1["volatility"] + h2["volatility"]) * 0.5
        if score > best_score:
            best_score = score
            best_window = f"{h1['hour']:02d}:00-{h2['hour']+1:02d}:00"

    return {
        "hourly": hourly_list,
        "best_window": best_window,
        "best_window_score": round(best_score, 2) if best_score > -1 else None,
    }


# ============================================================================
# 6. Trend Persistence Analysis
# ============================================================================

def trend_persistence_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Measure average bullish/bearish run lengths, consecutive candle stats.
    """
    df = df.copy()
    close = df["close"].astype(float)
    returns = close.pct_change().fillna(0)

    bullish = returns > 0
    runs = []
    current_run = 0
    current_dir = None

    for is_bull in bullish:
        if is_bull:
            if current_dir == "bull":
                current_run += 1
            else:
                if current_dir is not None:
                    runs.append((current_dir, current_run))
                current_dir = "bull"
                current_run = 1
        else:
            if current_dir == "bear":
                current_run += 1
            else:
                if current_dir is not None:
                    runs.append((current_dir, current_run))
                current_dir = "bear"
                current_run = 1

    if current_dir is not None:
        runs.append((current_dir, current_run))

    bull_runs = [r for d, r in runs if d == "bull"]
    bear_runs = [r for d, r in runs if d == "bear"]

    avg_bull_run = float(np.mean(bull_runs)) if bull_runs else 0.0
    avg_bear_run = float(np.mean(bear_runs)) if bear_runs else 0.0
    max_bull_run = int(max(bull_runs)) if bull_runs else 0
    max_bear_run = int(max(bear_runs)) if bear_runs else 0

    n_runs = len(runs)
    n_bull = len(bull_runs)
    n_bear = len(bear_runs)
    expected_runs = (2 * n_bull * n_bear) / (n_bull + n_bear) + 1 if (n_bull + n_bear) > 0 else 0
    variance = (2 * n_bull * n_bear * (2 * n_bull * n_bear - n_bull - n_bear)) / ((n_bull + n_bear) ** 2 * (n_bull + n_bear - 1)) if (n_bull + n_bear) > 1 else 0

    z_score = (n_runs - expected_runs) / np.sqrt(variance) if variance > 0 else 0
    persistence = "trending" if z_score < -1.96 else "mean_reverting" if z_score > 1.96 else "random"

    return {
        "avg_bullish_run_length": round(avg_bull_run, 2),
        "avg_bearish_run_length": round(avg_bear_run, 2),
        "max_bullish_run": max_bull_run,
        "max_bearish_run": max_bear_run,
        "consecutive_stats": {
            "total_runs": n_runs,
            "expected_runs": round(expected_runs, 2),
            "z_score": round(z_score, 3),
        },
        "directional_persistence": persistence,
    }


# ============================================================================
# 7. Volatility Structure Analysis
# ============================================================================

def volatility_structure_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    ATR percentiles, volatility clustering, regime transitions, forecasts.
    """
    df = df.copy()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.rolling(14).mean().fillna(0)

    returns = close.pct_change().fillna(0)
    rolling_vol = returns.rolling(20).std().fillna(0) * np.sqrt(252) * 100

    atr_p = np.percentile(atr.dropna(), [10, 25, 50, 75, 90])

    # EWMA volatility clustering over full series
    var_t = returns.var()
    for r in returns:
        var_t = 0.94 * var_t + 0.06 * r ** 2
    ewma_vol = np.sqrt(var_t) * np.sqrt(252) * 100

    # Volatility regime transitions
    vol_high = rolling_vol > np.percentile(rolling_vol.dropna(), 75)
    vol_low = rolling_vol < np.percentile(rolling_vol.dropna(), 25)
    transitions = int((vol_high != vol_high.shift(1)).sum() + (vol_low != vol_low.shift(1)).sum())

    return {
        "atr_percentiles": {
            "p10": round(float(atr_p[0]), 4),
            "p25": round(float(atr_p[1]), 4),
            "p50": round(float(atr_p[2]), 4),
            "p75": round(float(atr_p[3]), 4),
            "p90": round(float(atr_p[4]), 4),
        },
        "current_atr": round(float(atr.iloc[-1]), 4) if len(atr) > 0 else 0,
        "volatility_clustering": round(float(ewma_vol), 2),
        "volatility_regime_transitions": transitions,
        "volatility_forecast_pct": round(float(ewma_vol), 2),
        "current_volatility_pct": round(float(rolling_vol.iloc[-1]), 2) if len(rolling_vol) > 0 else 0,
    }


# ============================================================================
# 8. Tail Risk Analysis
# ============================================================================

def tail_risk_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    3-sigma, 5-sigma events, flash crash frequency, extreme move probability.
    Uses full data — no sampling.
    """
    df = df.copy()
    returns = df["close"].pct_change().dropna().astype(float).values

    if len(returns) < 30:
        return {"error": "insufficient data"}

    mu = float(np.mean(returns))
    sigma = float(np.std(returns))

    three_sigma = np.abs(returns - mu) > 3 * sigma
    five_sigma = np.abs(returns - mu) > 5 * sigma

    sigma3_count = int(three_sigma.sum())
    sigma5_count = int(five_sigma.sum())
    sigma3_freq = round(sigma3_count / len(returns) * 100, 3)
    sigma5_freq = round(sigma5_count / len(returns) * 100, 3)

    # Flash crash: > 5% single-bar drop
    flash_crash = returns < -0.05
    flash_crash_count = int(flash_crash.sum())
    flash_crash_freq = round(flash_crash_count / len(returns) * 100, 3)

    # Extreme move probability: fit t-distribution on full data
    try:
        df_t, loc, scale = stats.t.fit(returns)
        extreme_prob = 1 - stats.t.cdf(3 * sigma + mu, df_t, loc=loc, scale=scale)
    except Exception:
        extreme_prob = 0.00135  # normal 3-sigma fallback

    return {
        "three_sigma_events": sigma3_count,
        "three_sigma_freq_pct": sigma3_freq,
        "five_sigma_events": sigma5_count,
        "five_sigma_freq_pct": sigma5_freq,
        "flash_crash_count": flash_crash_count,
        "flash_crash_freq_pct": flash_crash_freq,
        "extreme_move_probability": round(extreme_prob * 100, 4),
        "kurtosis": round(float(stats.kurtosis(returns)), 3),
        "skewness": round(float(stats.skew(returns)), 3),
    }


# ============================================================================
# 9. Order Flow Proxies
# ============================================================================

def order_flow_proxies(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Estimate buy/sell volume, delta, and cumulative delta using tick approximation.
    """
    df = df.copy()
    close = df["close"].astype(float).values
    high = df["high"].astype(float).values
    low = df["low"].astype(float).values
    volume = df["volume"].astype(float).values if "volume" in df.columns else np.ones(len(df))

    range_ = high - low
    range_ = np.where(range_ == 0, np.nan, range_)

    buy_pct = (close - low) / range_
    buy_pct = np.where(np.isnan(buy_pct), 0.5, buy_pct)
    buy_pct = np.clip(buy_pct, 0, 1)

    buy_volume = volume * buy_pct
    sell_volume = volume * (1 - buy_pct)
    delta = buy_volume - sell_volume
    cumulative_delta = np.cumsum(delta)

    return {
        "buy_volume_total": round(float(buy_volume.sum()), 0),
        "sell_volume_total": round(float(sell_volume.sum()), 0),
        "net_delta": round(float(delta.sum()), 0),
        "cumulative_delta_latest": round(float(cumulative_delta[-1]), 0) if len(cumulative_delta) > 0 else 0,
        "delta_trend": "bullish" if float(delta.sum()) > 0 else "bearish",
        "buy_sell_ratio": round(float(buy_volume.sum() / max(sell_volume.sum(), 1)), 2),
    }


# ============================================================================
# 10. Multi-Timeframe Analysis
# ============================================================================

def multi_timeframe_analysis(
    symbol: str,
    client: Any,
    intervals: List[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze the same symbol across multiple timeframes and classify each.
    """
    from backend.services.data_service import normalize_symbol, slice_dataframe_by_date
    from backend.services.data_aggregator import aggregate_data

    if intervals is None:
        intervals = ["ONE_MINUTE", "FIVE_MINUTE", "FIFTEEN_MINUTE", "THIRTY_MINUTE", "ONE_HOUR", "ONE_DAY"]

    normalized = normalize_symbol(symbol.upper(), "ONE_MINUTE", client)
    results = {}

    for interval in intervals:
        df = client.load_dataset_csv(normalized, interval.upper())
        if df is None or df.empty:
            df = client.load_dataset_csv(symbol.upper(), interval.upper())
        if (df is None or df.empty) and client and getattr(client, "jwt_token", None):
            try:
                today = pd.Timestamp.now().normalize()
                sd = start_date or (today - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
                ed = end_date or today.strftime("%Y-%m-%d")
                df, status = aggregate_data(normalized, interval, sd, ed, client)
                if status not in ("mock", "failed") and df is not None and not df.empty:
                    client.save_dataset_csv(normalized, interval, df, is_mock=False)
            except Exception as e:
                print(f"WARN: Auto-download failed for {normalized} {interval}: {e}")

        if df is None or df.empty:
            results[interval] = {"status": "no_data", "classification": "unknown"}
            continue

        if start_date and end_date:
            try:
                df = slice_dataframe_by_date(df, start_date, end_date)
            except Exception:
                pass

        if len(df) < 20:
            results[interval] = {"status": "insufficient_data", "classification": "unknown"}
            continue

        close = df["close"].astype(float)
        returns = close.pct_change().fillna(0)
        hurst = hurst_exponent(close)
        trend = trend_persistence_analysis(df)
        vol = volatility_structure_analysis(df)

        if hurst.get("hurst") is not None and hurst["hurst"] < 0.45:
            classification = "Mean Reverting"
        elif hurst.get("hurst") is not None and hurst["hurst"] > 0.55:
            classification = "Trending"
        elif trend.get("directional_persistence") == "trending":
            classification = "Trending"
        elif trend.get("directional_persistence") == "mean_reverting":
            classification = "Mean Reverting"
        else:
            classification = "Neutral"

        results[interval] = {
            "classification": classification,
            "hurst": hurst.get("hurst"),
            "trend_persistence": trend.get("directional_persistence"),
            "current_volatility": vol.get("current_volatility_pct"),
        }

    return results


# ============================================================================
# 12. Factor Exposure Analysis
# ============================================================================

def factor_exposure_analysis(
    df: pd.DataFrame,
    benchmark_dfs: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    Measure sensitivity of the symbol to various benchmarks (NIFTY, BANKNIFTY, etc.).
    """
    if df is None or df.empty or "close" not in df.columns:
        return {"error": "No data"}

    sym_returns = df["close"].pct_change().dropna().astype(float)
    exposures = {}

    for factor_name, factor_df in benchmark_dfs.items():
        if factor_df is None or factor_df.empty or "close" not in factor_df.columns:
            continue
        factor_returns = factor_df["close"].pct_change().dropna().astype(float)
        aligned = pd.concat([sym_returns, factor_returns], axis=1).dropna()
        if len(aligned) < 20:
            continue

        x = aligned.iloc[:, 1].values.reshape(-1, 1)
        y = aligned.iloc[:, 0].values
        model = LinearRegression()
        model.fit(x, y)
        r2 = model.score(x, y)
        beta = float(model.coef_[0])
        alpha = float(model.intercept_)
        correlation = float(np.corrcoef(y, x.flatten())[0, 1])

        exposures[factor_name] = {
            "beta": round(beta, 4),
            "alpha": round(alpha, 6),
            "r_squared": round(r2, 4),
            "correlation": round(correlation, 4),
        }

    return exposures


# ============================================================================
# 13. Walk-Forward Stability Analysis
# ============================================================================

def walk_forward_stability_analysis(
    df: pd.DataFrame,
    windows: List[str] = None,
) -> Dict[str, Any]:
    """
    Run mean reversion, trend, and volatility analysis on multiple lookback windows.
    """
    if windows is None:
        windows = ["1M", "3M", "6M"]

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")
    now = df["time"].iloc[-1]

    window_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    results = {}

    for w in windows:
        days = window_days.get(w, 30)
        start = now - pd.Timedelta(days=days)
        mask = df["time"] >= start
        window_df = df[mask].copy()

        if len(window_df) < 30:
            results[w] = {"status": "insufficient_data"}
            continue

        close = window_df["close"].astype(float)
        hurst = hurst_exponent(close)
        trend = trend_persistence_analysis(window_df)
        tail = tail_risk_analysis(window_df)
        vol = volatility_structure_analysis(window_df)
        mr = mean_reversion_analysis(close)

        results[w] = {
            "bars": len(window_df),
            "mean_reversion": mr,
            "trend_persistence": trend,
            "tail_risk": tail,
            "volatility": vol,
            "status": "ok",
        }

    return results


# ============================================================================
# 14. Feature Importance Engine
# ============================================================================

def feature_importance_engine(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluate predictive power of common technical features using forward-return correlation.
    """
    df = df.copy()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

    returns = close.pct_change().fillna(0)
    forward_return = returns.shift(-1).fillna(0)

    features = {}

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    features["rsi"] = rsi

    # ATR
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    features["atr"] = atr

    # ADX (simplified)
    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * plus_dm.rolling(14).mean() / atr_safe
    minus_di = 100 * minus_dm.rolling(14).mean() / atr_safe
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan) * 100).fillna(0)
    adx = dx.rolling(14).mean()
    features["adx"] = adx

    # VWAP distance
    typical = (high + low + close) / 3
    vwap = (typical * volume).cumsum() / volume.cumsum()
    vwap_dist = (close - vwap) / vwap * 100
    features["vwap_distance"] = vwap_dist

    # Volume spikes
    vol_sma = volume.rolling(20).mean()
    vol_spike = volume / vol_sma.replace(0, np.nan)
    features["volume_spike"] = vol_spike

    # Bollinger deviation
    bb_sma = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_dev = (close - bb_sma) / bb_std.replace(0, np.nan)
    features["bollinger_dev"] = bb_dev

    # Evaluate predictive power
    importance = {}
    for name, feat in features.items():
        aligned = pd.concat([feat, forward_return], axis=1).dropna()
        if len(aligned) < 20:
            importance[name] = {"correlation": None, "predictive_power": 0}
            continue
        corr = float(np.corrcoef(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1])
        p_value = 0.5
        try:
            _, p_value = stats.pearsonr(aligned.iloc[:, 0], aligned.iloc[:, 1])
        except Exception:
            pass
        power = abs(corr) * 100
        if p_value < 0.05:
            power += 10
        if p_value < 0.01:
            power += 10
        importance[name] = {
            "correlation": round(corr, 4),
            "p_value": round(p_value, 4),
            "predictive_power": min(100, round(power, 1)),
        }

    sorted_features = sorted(importance.items(), key=lambda x: x[1]["predictive_power"], reverse=True)

    return {
        "feature_importance": importance,
        "ranked_features": [{"feature": k, **v} for k, v in sorted_features],
        "best_feature": sorted_features[0][0] if sorted_features else None,
    }
