"""
Deep Dataset Analyzer — comprehensive statistical analysis of OHLCV CSV/Excel data.

Independent of backtest results. Analyzes raw market data to help traders decide
which strategy type may be appropriate (trend-following, mean-reversion, breakout, etc.)

Produces:
- Descriptive price statistics
- Return analysis (distribution, tail risk, autocorrelation)
- Volatility analysis (regimes, clustering, forecast)
- Trend & momentum diagnostics
- Support / resistance levels
- Volume insights
- Regime classification
- Seasonality patterns
- Candlestick pattern frequency
- Terminal-style narrative logs
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from scipy import stats


def analyze_dataset(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    interval: str = "UNKNOWN",
) -> Dict[str, Any]:
    """
    Run comprehensive analysis on a single-symbol OHLCV DataFrame.

    Args:
        df: DataFrame with columns [time, open, high, low, close, volume]
        symbol: instrument symbol for labeling
        interval: candle interval for labeling

    Returns:
        Dict with statistics, plot-ready series, and terminal narrative logs.
    """
    logs: List[str] = []
    df = df.copy()
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time', 'open', 'high', 'low', 'close'])
    df = df.sort_values('time').reset_index(drop=True)

    n_bars = len(df)
    if n_bars < 10:
        logs.append(f"[ERROR] Dataset too small ({n_bars} bars). Need at least 10 bars for meaningful analysis.")
        return {"logs": logs, "valid": False}

    logs.append(f"[INFO] Analyzing {symbol} @ {interval} — {n_bars} bars loaded")

    # ========== 1. PRICE STATISTICS ==========
    price_stats = _analyze_prices(df, logs)

    # ========== 2. RETURNS ANALYSIS ==========
    returns_analysis = _analyze_returns(df, logs)

    # ========== 3. VOLATILITY ANALYSIS ==========
    vol_analysis = _analyze_volatility(df, logs)

    # ========== 4. TREND & MOMENTUM ==========
    trend_analysis = _analyze_trend(df, logs)

    # ========== 5. DRAWDOWN ANALYSIS ==========
    dd_analysis = _analyze_drawdown(df, logs)

    # ========== 6. SUPPORT / RESISTANCE ==========
    levels = _find_support_resistance(df, logs)

    # ========== 7. VOLUME ANALYSIS ==========
    vol_insights = _analyze_volume(df, logs)

    # ========== 8. REGIME CLASSIFICATION ==========
    from engine.research import classify_market_regimes
    df_regime = classify_market_regimes(df)
    regime_counts = df_regime['regime'].value_counts().to_dict()
    regime_pct = {k: round(v / n_bars * 100, 1) for k, v in regime_counts.items()}
    logs.append(f"[REGIME] Market character: {regime_pct}")

    # ========== 9. SEASONALITY ==========
    seasonality = _analyze_seasonality(df, interval, logs)

    # ========== 10. CANDLESTICK PATTERNS ==========
    patterns = _detect_candlestick_patterns(df, logs)

    # ========== 11. AUTOCORRELATION ==========
    autocorr = _analyze_autocorrelation(df, logs)

    # ========== 12. STRATEGY SUITABILITY SCORE ==========
    suitability = _score_strategy_suitability(
        returns_analysis, trend_analysis, vol_analysis, regime_pct, logs
    )

    # Build plot-ready series (frontend can render directly)
    plot_series = {
        "time": df['time'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
        "open": df['open'].tolist(),
        "high": df['high'].tolist(),
        "low": df['low'].tolist(),
        "close": df['close'].tolist(),
        "volume": df.get('volume', pd.Series([0]*n_bars)).tolist(),
        "returns": returns_analysis["returns_series"],
        "cumulative_returns": returns_analysis["cumulative_returns_series"],
        "rolling_vol_20": vol_analysis["rolling_vol_20_series"],
        "drawdown": dd_analysis["drawdown_series"],
        "regime": df_regime['regime'].tolist(),
        "ema_fast": trend_analysis["ema_fast_series"],
        "ema_slow": trend_analysis["ema_slow_series"],
    }

    return {
        "valid": True,
        "symbol": symbol,
        "interval": interval,
        "bars": n_bars,
        "date_range": {
            "start": str(df['time'].iloc[0]),
            "end": str(df['time'].iloc[-1]),
        },
        "logs": logs,
        "price_stats": price_stats,
        "returns": returns_analysis["summary"],
        "volatility": vol_analysis["summary"],
        "trend": trend_analysis["summary"],
        "drawdown": dd_analysis["summary"],
        "levels": levels,
        "volume": vol_insights,
        "regimes": regime_pct,
        "seasonality": seasonality,
        "patterns": patterns,
        "autocorrelation": autocorr,
        "suitability": suitability,
        "plot_series": plot_series,
    }


def _analyze_prices(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    body = (c - o).abs()
    range_ = h - l
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    stats_dict = {
        "open_mean": round(float(o.mean()), 2),
        "high_max": round(float(h.max()), 2),
        "low_min": round(float(l.min()), 2),
        "close_mean": round(float(c.mean()), 2),
        "close_std": round(float(c.std()), 2),
        "avg_body": round(float(body.mean()), 2),
        "avg_range": round(float(range_.mean()), 2),
        "avg_upper_wick": round(float(upper_wick.mean()), 2),
        "avg_lower_wick": round(float(lower_wick.mean()), 2),
        "body_to_range_ratio": round(float((body / range_.replace(0, np.nan)).mean()), 3),
    }

    logs.append(f"[PRICE] Avg range: Rs.{stats_dict['avg_range']:.2f} | Body/Range: {stats_dict['body_to_range_ratio']:.2f}")
    if stats_dict['body_to_range_ratio'] > 0.6:
        logs.append(f"[PRICE] Strong directional candles — trend strategies may work well")
    elif stats_dict['body_to_range_ratio'] < 0.3:
        logs.append(f"[PRICE] Weak bodies, long wicks — ranging/mean-reversion environment likely")

    return stats_dict


def _analyze_returns(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    returns = df['close'].pct_change().dropna()
    cum_returns = (1 + returns).cumprod() - 1

    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns))
    jarque_bera_stat, jarque_bera_p = stats.jarque_bera(returns)

    # Tail risk
    var_95 = float(np.percentile(returns, 5))
    var_99 = float(np.percentile(returns, 1))
    cvar_95 = float(returns[returns <= var_95].mean()) if len(returns[returns <= var_95]) > 0 else var_95

    # Positive vs negative days
    pos_pct = float((returns > 0).sum() / len(returns) * 100)
    neg_pct = float((returns < 0).sum() / len(returns) * 100)

    summary = {
        "mean_return_pct": round(float(returns.mean()) * 100, 4),
        "std_return_pct": round(float(returns.std()) * 100, 4),
        "annualized_return_pct": round(float(returns.mean()) * 252 * 100, 2) if len(returns) > 50 else None,
        "annualized_vol_pct": round(float(returns.std()) * np.sqrt(252) * 100, 2),
        "sharpe_approx": round(float(returns.mean()) / float(returns.std()) * np.sqrt(252), 2) if returns.std() > 0 else 0,
        "skewness": round(skew, 3),
        "kurtosis": round(kurt, 3),
        "jarque_bera_p": round(float(jarque_bera_p), 4),
        "is_normal": bool(jarque_bera_p > 0.05),
        "var_95_pct": round(var_95 * 100, 3),
        "var_99_pct": round(var_99 * 100, 3),
        "cvar_95_pct": round(cvar_95 * 100, 3),
        "positive_bars_pct": round(pos_pct, 1),
        "negative_bars_pct": round(neg_pct, 1),
        "max_single_gain_pct": round(float(returns.max()) * 100, 3),
        "max_single_loss_pct": round(float(returns.min()) * 100, 3),
    }

    logs.append(f"[RETURNS] Mean: {summary['mean_return_pct']:.4f}% | Std: {summary['std_return_pct']:.4f}% | AnnVol: {summary['annualized_vol_pct']:.1f}%")
    logs.append(f"[RETURNS] Skew: {summary['skewness']:.2f} | Kurt: {summary['kurtosis']:.2f} | Normal? {summary['is_normal']}")
    logs.append(f"[RETURNS] VaR(95): {summary['var_95_pct']:.3f}% | CVaR(95): {summary['cvar_95_pct']:.3f}%")

    if summary['skewness'] < -0.5:
        logs.append(f"[RETURNS] Negative skew — large downside tail risk. Tight stops recommended.")
    if summary['kurtosis'] > 3:
        logs.append(f"[RETURNS] Fat tails (leptokurtic) — expect occasional extreme moves.")

    return {
        "summary": summary,
        "returns_series": [round(float(r) * 100, 4) for r in returns],
        "cumulative_returns_series": [round(float(r) * 100, 4) for r in cum_returns],
    }


def _analyze_volatility(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    returns = df['close'].pct_change().dropna()
    rolling_vol_20 = returns.rolling(20).std() * np.sqrt(252) * 100
    rolling_vol_50 = returns.rolling(50).std() * np.sqrt(252) * 100

    # Realized volatility (annualized)
    realized_vol = float(returns.std() * np.sqrt(252) * 100)

    # Volatility of volatility
    vol_of_vol = float(rolling_vol_20.dropna().std())

    # GARCH-like simple estimate: EWMA variance
    lambda_ = 0.94
    variances = [returns.var()]
    for r in returns.iloc[1:]:
        variances.append(lambda_ * variances[-1] + (1 - lambda_) * r ** 2)
    ewma_vol = float(np.sqrt(variances[-1]) * np.sqrt(252) * 100)

    # Volatility regime (compare current to historical)
    current_vol = float(rolling_vol_20.dropna().iloc[-1]) if len(rolling_vol_20.dropna()) > 0 else realized_vol
    vol_median = float(rolling_vol_20.dropna().median()) if len(rolling_vol_20.dropna()) > 0 else realized_vol

    if current_vol > vol_median * 1.3:
        vol_regime = "HIGH"
    elif current_vol < vol_median * 0.7:
        vol_regime = "LOW"
    else:
        vol_regime = "MODERATE"

    summary = {
        "realized_vol_annual_pct": round(realized_vol, 2),
        "ewma_vol_annual_pct": round(ewma_vol, 2),
        "vol_of_vol": round(vol_of_vol, 2),
        "current_vol_regime": vol_regime,
        "current_vol_pct": round(current_vol, 2),
        "vol_median_pct": round(vol_median, 2),
        "vol_max_pct": round(float(rolling_vol_20.max()), 2) if not rolling_vol_20.isna().all() else realized_vol,
        "vol_min_pct": round(float(rolling_vol_20.min()), 2) if not rolling_vol_20.isna().all() else realized_vol,
    }

    logs.append(f"[VOL] Realized: {summary['realized_vol_annual_pct']:.1f}% | EWMA: {summary['ewma_vol_annual_pct']:.1f}% | Regime: {vol_regime}")
    if vol_regime == "HIGH":
        logs.append(f"[VOL] Elevated volatility — reduce position size, widen stops, or trade breakouts")
    elif vol_regime == "LOW":
        logs.append(f"[VOL] Compressed volatility — potential expansion ahead. Watch for breakout setups")

    return {
        "summary": summary,
        "rolling_vol_20_series": [round(float(v), 2) if not pd.isna(v) else None for v in rolling_vol_20],
    }


def _analyze_trend(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    closes = df['close'].values
    x = np.arange(len(closes))

    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)
    r_squared = r_value ** 2

    # EMAs
    ema_20 = df['close'].ewm(span=20, adjust=False).mean()
    ema_50 = df['close'].ewm(span=50, adjust=False).mean()

    # Trend direction
    last_price = float(closes[-1])
    ema20_last = float(ema_20.iloc[-1])
    ema50_last = float(ema_50.iloc[-1])

    if ema20_last > ema50_last * 1.005:
        trend_direction = "BULLISH"
    elif ema20_last < ema50_last * 0.995:
        trend_direction = "BEARISH"
    else:
        trend_direction = "NEUTRAL"

    # ADX-like proxy using directional movement
    tr = np.maximum(df['high'] - df['low'],
                    np.maximum((df['high'] - df['close'].shift(1)).abs(),
                               (df['low'] - df['close'].shift(1)).abs()))
    atr = tr.rolling(14).mean()
    plus_dm = (df['high'] - df['high'].shift(1)).clip(lower=0)
    minus_dm = (df['low'].shift(1) - df['low']).clip(lower=0)
    plus_di = 100 * plus_dm.rolling(14).mean() / atr
    minus_di = 100 * minus_dm.rolling(14).mean() / atr
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan) * 100).fillna(0)
    adx_proxy = dx.rolling(14).mean().iloc[-1] if len(dx) >= 14 else 0

    summary = {
        "linear_slope": round(float(slope), 4),
        "r_squared": round(float(r_squared), 4),
        "trend_p_value": round(float(p_value), 4),
        "is_trending": bool(r_squared > 0.3 and p_value < 0.05),
        "trend_direction": trend_direction,
        "ema20": round(ema20_last, 2),
        "ema50": round(ema50_last, 2),
        "price_vs_ema20_pct": round((last_price - ema20_last) / ema20_last * 100, 2),
        "price_vs_ema50_pct": round((last_price - ema50_last) / ema50_last * 100, 2),
        "adx_proxy": round(float(adx_proxy), 2),
        "strong_trend": bool(float(adx_proxy) > 25),
    }

    logs.append(f"[TREND] Direction: {trend_direction} | R²: {summary['r_squared']:.3f} | ADX-proxy: {summary['adx_proxy']:.1f}")
    if summary['is_trending']:
        logs.append(f"[TREND] Statistically significant trend detected — momentum/trend-following strategies favored")
    else:
        logs.append(f"[TREND] Weak linear trend — mean-reversion or range-bound strategies may be more suitable")

    return {
        "summary": summary,
        "ema_fast_series": [round(float(v), 2) for v in ema_20],
        "ema_slow_series": [round(float(v), 2) for v in ema_50],
    }


def _analyze_drawdown(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    prices = df['close']
    peak = prices.cummax()
    drawdown = (prices - peak) / peak * 100
    max_dd = float(drawdown.min())
    max_dd_idx = int(drawdown.idxmin())

    # Find recovery times
    underwater = drawdown < 0
    dd_periods = []
    in_dd = False
    start_idx = 0
    for i, is_dd in enumerate(underwater):
        if is_dd and not in_dd:
            in_dd = True
            start_idx = i
        elif not is_dd and in_dd:
            in_dd = False
            dd_periods.append(i - start_idx)
    if in_dd:
        dd_periods.append(len(underwater) - start_idx)

    avg_dd_duration = float(np.mean(dd_periods)) if dd_periods else 0
    max_dd_duration = int(max(dd_periods)) if dd_periods else 0

    summary = {
        "max_drawdown_pct": round(max_dd, 2),
        "max_dd_date": str(df['time'].iloc[max_dd_idx]) if max_dd_idx < len(df) else None,
        "avg_drawdown_duration_bars": round(avg_dd_duration, 1),
        "max_drawdown_duration_bars": max_dd_duration,
        "current_drawdown_pct": round(float(drawdown.iloc[-1]), 2),
        "underwater_pct": round(float(underwater.sum()) / len(underwater) * 100, 1),
    }

    logs.append(f"[DD] Max Drawdown: {summary['max_drawdown_pct']:.2f}% | Avg DD Duration: {summary['avg_drawdown_duration_bars']:.0f} bars")
    logs.append(f"[DD] Currently underwater: {summary['current_drawdown_pct']:.2f}% | Time underwater: {summary['underwater_pct']:.1f}%")

    if max_dd < -10:
        logs.append(f"[DD] Deep historical drawdowns — conservative sizing essential")
    if summary['underwater_pct'] > 50:
        logs.append(f"[DD] Spends >50% of time underwater — buy-and-hold is painful here")

    return {
        "summary": summary,
        "drawdown_series": [round(float(v), 2) for v in drawdown],
    }


def _find_support_resistance(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    window = min(20, len(df) // 4)
    if window < 5:
        return {"pivots": [], "rolling_high": None, "rolling_low": None}

    rolling_high = float(df['high'].rolling(window).max().iloc[-1])
    rolling_low = float(df['low'].rolling(window).min().iloc[-1])
    current = float(df['close'].iloc[-1])

    # Simple pivot detection (local minima/maxima)
    highs = df['high'].values
    lows = df['low'].values
    pivots = []
    for i in range(window, len(df) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            pivots.append({"type": "resistance", "price": round(float(highs[i]), 2), "idx": i})
        if lows[i] == min(lows[i - window:i + window + 1]):
            pivots.append({"type": "support", "price": round(float(lows[i]), 2), "idx": i})

    # Cluster nearby levels
    levels = []
    for p in pivots:
        merged = False
        for l in levels:
            if abs(l['price'] - p['price']) / l['price'] < 0.005:  # 0.5% tolerance
                l['price'] = (l['price'] * l['strength'] + p['price']) / (l['strength'] + 1)
                l['strength'] += 1
                merged = True
                break
        if not merged:
            levels.append({"price": p['price'], "strength": 1, "type": p['type']})

    levels = sorted(levels, key=lambda x: x['strength'], reverse=True)[:8]

    # Distance to nearest levels
    above = [l for l in levels if l['price'] > current]
    below = [l for l in levels if l['price'] < current]
    nearest_resistance = min(above, key=lambda x: x['price'] - current) if above else None
    nearest_support = max(below, key=lambda x: current - x['price']) if below else None

    logs.append(f"[LEVELS] Rolling {window}-bar High: Rs.{rolling_high:.2f} | Low: Rs.{rolling_low:.2f}")
    if nearest_resistance:
        logs.append(f"[LEVELS] Nearest resistance: Rs.{nearest_resistance['price']:.2f} (strength {nearest_resistance['strength']})")
    if nearest_support:
        logs.append(f"[LEVELS] Nearest support: Rs.{nearest_support['price']:.2f} (strength {nearest_support['strength']})")

    return {
        "pivots": levels,
        "rolling_high": round(rolling_high, 2),
        "rolling_low": round(rolling_low, 2),
        "nearest_resistance": nearest_resistance,
        "nearest_support": nearest_support,
        "distance_to_resistance_pct": round((nearest_resistance['price'] - current) / current * 100, 2) if nearest_resistance else None,
        "distance_to_support_pct": round((current - nearest_support['price']) / current * 100, 2) if nearest_support else None,
    }


def _analyze_volume(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    if 'volume' not in df.columns or df['volume'].isna().all():
        logs.append("[VOLUME] No volume data available")
        return {"available": False}

    vol = df['volume']
    returns = df['close'].pct_change().dropna()
    vol_change = vol.pct_change().dropna()

    # Volume-price correlation
    vol_price_corr = float(vol.corr(returns.abs())) if len(vol) == len(returns.abs()) else 0

    # Relative volume (current vs 20-bar average)
    vol_sma20 = vol.rolling(20).mean()
    rel_vol = float(vol.iloc[-1] / vol_sma20.iloc[-1]) if vol_sma20.iloc[-1] > 0 else 1.0

    summary = {
        "available": True,
        "avg_volume": int(vol.mean()),
        "max_volume": int(vol.max()),
        "min_volume": int(vol.min()),
        "volume_price_corr": round(vol_price_corr, 3),
        "relative_volume": round(rel_vol, 2),
        "volume_trend": "RISING" if float(vol.iloc[-5:].mean()) > float(vol.iloc[-20:-5].mean()) else "FALLING",
    }

    logs.append(f"[VOLUME] Avg: {summary['avg_volume']:,} | RelVol: {summary['relative_volume']:.2f}x | Vol-Price corr: {summary['volume_price_corr']:.3f}")
    if rel_vol > 1.5:
        logs.append(f"[VOLUME] Volume spike detected — confirms price move strength")
    if vol_price_corr > 0.3:
        logs.append(f"[VOLUME] Volume confirms price moves — good for breakout strategies")

    return summary


def _analyze_seasonality(df: pd.DataFrame, interval: str, logs: List[str]) -> Dict[str, Any]:
    returns = df['close'].pct_change().dropna()
    df['returns'] = returns
    df['hour'] = df['time'].dt.hour
    df['dow'] = df['time'].dt.dayofweek  # 0=Monday
    df['month'] = df['time'].dt.month

    result = {}

    # Hour-of-day (for intraday)
    if interval.upper() not in ["ONE_DAY", "DAILY", "1D"]:
        hourly = df.groupby('hour')['returns'].agg(['mean', 'std', 'count']).reset_index()
        hourly = hourly[hourly['count'] >= 5]  # need at least 5 observations
        if not hourly.empty:
            best_hour = hourly.loc[hourly['mean'].idxmax()]
            worst_hour = hourly.loc[hourly['mean'].idxmin()]
            result['hourly'] = {
                "best_hour": int(best_hour['hour']),
                "best_hour_return_pct": round(float(best_hour['mean']) * 100, 4),
                "worst_hour": int(worst_hour['hour']),
                "worst_hour_return_pct": round(float(worst_hour['mean']) * 100, 4),
                "hourly_data": hourly.to_dict(orient='records'),
            }
            logs.append(f"[SEASONALITY] Best hour: {best_hour['hour']}:00 ({result['hourly']['best_hour_return_pct']:.4f}%) | Worst: {worst_hour['hour']}:00 ({result['hourly']['worst_hour_return_pct']:.4f}%)")

    # Day-of-week (for daily+ or if enough intraday data)
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow = df.groupby('dow')['returns'].agg(['mean', 'std', 'count']).reset_index()
    dow = dow[dow['count'] >= 3]
    if not dow.empty:
        best_dow = dow.loc[dow['mean'].idxmax()]
        worst_dow = dow.loc[dow['mean'].idxmin()]
        result['dow'] = {
            "best_day": dow_names[int(best_dow['dow'])],
            "best_day_return_pct": round(float(best_dow['mean']) * 100, 4),
            "worst_day": dow_names[int(worst_dow['dow'])],
            "worst_day_return_pct": round(float(worst_dow['mean']) * 100, 4),
            "dow_data": [{"day": dow_names[int(r['dow'])], "mean_return_pct": round(float(r['mean']) * 100, 4), "count": int(r['count'])} for _, r in dow.iterrows()],
        }
        logs.append(f"[SEASONALITY] Best day: {dow_names[int(best_dow['dow'])]} | Worst: {dow_names[int(worst_dow['dow'])]}")

    if not result:
        logs.append("[SEASONALITY] Insufficient data for seasonality analysis")

    return result


def _detect_candlestick_patterns(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    body = (c - o).abs()
    range_ = h - l
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    doji = body / range_.replace(0, np.nan) < 0.1
    hammer = (lower_wick > body * 2) & (upper_wick < body * 0.5) & (c > o)
    shooting_star = (upper_wick > body * 2) & (lower_wick < body * 0.5) & (c < o)
    engulfing_bull = (c > o) & (c.shift(1) < o.shift(1)) & (c > o.shift(1)) & (o < c.shift(1))
    engulfing_bear = (c < o) & (c.shift(1) > o.shift(1)) & (c < o.shift(1)) & (o > c.shift(1))

    patterns = {
        "doji_count": int(doji.sum()),
        "doji_pct": round(float(doji.sum()) / len(df) * 100, 1),
        "hammer_count": int(hammer.sum()),
        "shooting_star_count": int(shooting_star.sum()),
        "bullish_engulfing_count": int(engulfing_bull.sum()),
        "bearish_engulfing_count": int(engulfing_bear.sum()),
    }

    logs.append(f"[PATTERNS] Doji: {patterns['doji_count']} ({patterns['doji_pct']}%) | Hammer: {patterns['hammer_count']} | Engulfing: {patterns['bullish_engulfing_count'] + patterns['bearish_engulfing_count']}")

    return patterns


def _analyze_autocorrelation(df: pd.DataFrame, logs: List[str]) -> Dict[str, Any]:
    returns = df['close'].pct_change().dropna()
    if len(returns) < 20:
        return {"lags": []}

    lags = [1, 5, 10, 20]
    results = []
    for lag in lags:
        if len(returns) > lag:
            corr = float(returns.autocorr(lag=lag))
            results.append({"lag": lag, "autocorr": round(corr, 3)})

    lag1 = next((r for r in results if r['lag'] == 1), None)
    if lag1:
        if lag1['autocorr'] > 0.1:
            logs.append(f"[AUTOCORR] Lag-1 autocorr: {lag1['autocorr']:.3f} — momentum/persistence detected")
        elif lag1['autocorr'] < -0.1:
            logs.append(f"[AUTOCORR] Lag-1 autocorr: {lag1['autocorr']:.3f} — mean-reversion signal")
        else:
            logs.append(f"[AUTOCORR] Lag-1 autocorr: {lag1['autocorr']:.3f} — close to random walk")

    return {"lags": results}


def _score_strategy_suitability(
    returns_analysis: Dict,
    trend_analysis: Dict,
    vol_analysis: Dict,
    regime_pct: Dict[str, float],
    logs: List[str],
) -> Dict[str, Any]:
    """
    Score different strategy types based on data characteristics.
    Returns scores 0-100 for each strategy family.
    """
    ret = returns_analysis["summary"]
    trend = trend_analysis["summary"]
    vol = vol_analysis["summary"]

    scores = {}

    # Trend Following: likes trending, moderate vol, positive autocorr
    trend_score = 0
    if trend["is_trending"]:
        trend_score += 40
    if trend["strong_trend"]:
        trend_score += 20
    if trend["trend_direction"] != "NEUTRAL":
        trend_score += 20
    if regime_pct.get("TRENDING_BULLISH", 0) + regime_pct.get("TRENDING_BEARISH", 0) > 40:
        trend_score += 20
    scores["trend_following"] = min(trend_score, 100)

    # Mean Reversion: likes ranging, negative autocorr, flat trend
    mr_score = 0
    if not trend["is_trending"]:
        mr_score += 30
    if regime_pct.get("QUIET_RANGING", 0) + regime_pct.get("VOLATILE_RANGING", 0) > 40:
        mr_score += 30
    if ret["skewness"] < 0:
        mr_score += 20
    if vol["current_vol_regime"] in ["LOW", "MODERATE"]:
        mr_score += 20
    scores["mean_reversion"] = min(mr_score, 100)

    # Breakout/Momentum: likes low vol compression, high vol expansion, volume confirmation
    breakout_score = 0
    if vol["current_vol_regime"] == "LOW":
        breakout_score += 30
    if vol["vol_of_vol"] > 5:
        breakout_score += 20
    if trend["strong_trend"]:
        breakout_score += 20
    if ret["kurtosis"] > 3:
        breakout_score += 15  # fat tails = explosive moves
    if regime_pct.get("GAP_DAY", 0) > 5:
        breakout_score += 15
    scores["breakout_momentum"] = min(breakout_score, 100)

    # Scalping: likes high vol, intraday, strong seasonality
    scalp_score = 0
    if vol["current_vol_regime"] == "HIGH":
        scalp_score += 30
    if vol["realized_vol_annual_pct"] > 30:
        scalp_score += 20
    if ret["mean_return_pct"] > 0:
        scalp_score += 20
    if trend["trend_direction"] == "NEUTRAL":
        scalp_score += 15
    scores["scalping"] = min(scalp_score, 100)

    # Buy & Hold: likes strong trend, low drawdown, positive skew
    bnh_score = 0
    if trend["is_trending"] and trend["trend_direction"] == "BULLISH":
        bnh_score += 40
    if ret["skewness"] > 0:
        bnh_score += 20
    if ret["annualized_return_pct"] and ret["annualized_return_pct"] > 10:
        bnh_score += 20
    if vol["current_vol_regime"] != "HIGH":
        bnh_score += 20
    scores["buy_and_hold"] = min(bnh_score, 100)

    # Pick best
    best = max(scores, key=scores.get)
    best_score = scores[best]

    logs.append(f"[SUITABILITY] Strategy scores: { {k: f'{v}/100' for k, v in scores.items()} }")
    logs.append(f"[SUITABILITY] >>> RECOMMENDED: {best.replace('_', ' ').upper()} ({best_score}/100)")

    if best_score < 40:
        logs.append(f"[SUITABILITY] WARNING: All scores are low — this instrument may be difficult to trade profitably")

    return {
        "scores": scores,
        "recommended": best,
        "recommended_score": best_score,
    }
