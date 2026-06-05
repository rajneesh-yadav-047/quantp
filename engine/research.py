import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

def classify_market_regimes(df: pd.DataFrame, fast_period: int = 20, slow_period: int = 50, atr_period: int = 14) -> pd.DataFrame:
    """
    Computes technical indicators and classifies each candle into a market regime:
    - TRENDING_BULLISH: Fast EMA > Slow EMA, ADX or Price Slope positive, volatility moderate.
    - TRENDING_BEARISH: Fast EMA < Slow EMA, Price Slope negative.
    - VOLATILE_RANGING: Flat EMAs, but high relative volatility (ATR).
    - QUIET_RANGING: Flat EMAs, low relative volatility (ATR).
    - GAP_DAY: Open differs significantly from previous Close (requires daily resampling or intraday first bar flag).
    """
    df = df.copy()
    if 'time' in df.columns:
        df = df.sort_values('time')
    
    # Calculate returns
    df['returns'] = df['close'].pct_change().fillna(0)
    
    # Calculate moving averages
    df['ema_fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    # Calculate True Range (TR) and ATR
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            (df['high'] - df['prev_close']).abs(),
            (df['low'] - df['prev_close']).abs()
        )
    )
    df['atr'] = df['tr'].rolling(window=atr_period).mean().fillna(method='bfill')
    df['atr_ma'] = df['atr'].rolling(window=atr_period * 2).mean().fillna(method='bfill')
    
    # Simple Gap detection: (open - prev_close) / prev_close
    df['gap_pct'] = ((df['open'] - df['prev_close']) / df['prev_close']).fillna(0)
    
    # Classification
    regimes = []
    for idx, row in df.iterrows():
        # Check gap
        if abs(row['gap_pct']) >= 0.005:  # 0.5% or more open gap
            regimes.append("GAP_DAY")
            continue
            
        is_trending = abs(row['ema_fast'] - row['ema_slow']) / row['ema_slow'] > 0.0025  # 0.25% spread
        
        if is_trending:
            if row['ema_fast'] > row['ema_slow']:
                regimes.append("TRENDING_BULLISH")
            else:
                regimes.append("TRENDING_BEARISH")
        else:
            # Ranging - check volatility relative to average ATR
            if row['atr'] > row['atr_ma']:
                regimes.append("VOLATILE_RANGING")
            else:
                regimes.append("QUIET_RANGING")
                
    df['regime'] = regimes
    return df

def attribute_performance_by_regime(
    candles_df_dict: Dict[str, pd.DataFrame],
    trades: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Segments trade results based on the market regime at the trade execution timestamp.
    """
    # Classify regimes for each symbol
    classified_dfs = {}
    for sym, df in candles_df_dict.items():
        classified_dfs[sym] = classify_market_regimes(df)
        
    # Map trade to regime
    regime_pnl: Dict[str, List[float]] = {
        "TRENDING_BULLISH": [],
        "TRENDING_BEARISH": [],
        "VOLATILE_RANGING": [],
        "QUIET_RANGING": [],
        "GAP_DAY": []
    }
    
    regime_counts = {k: 0 for k in regime_pnl.keys()}
    regime_win_counts = {k: 0 for k in regime_pnl.keys()}

    # Group trades by symbol to match faster
    trades_by_sym: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades:
        sym = t['symbol']
        if sym not in trades_by_sym:
            trades_by_sym[sym] = []
        trades_by_sym[sym].append(t)

    # Simple trade matching to associate sell-buys PnL (or use raw trades if matched trades are provided)
    # We can use our FIFO matched trades for PnL analysis!
    # Let's import match_trades_fifo from analytics
    from engine.analytics import match_trades_fifo
    matched_trades = match_trades_fifo(trades)

    for mt in matched_trades:
        sym = mt['symbol']
        sell_time = mt['sell_time']
        pnl = mt['pnl']
        
        # Look up regime of that symbol at sell_time (closing time)
        if sym in classified_dfs:
            df_sym = classified_dfs[sym]
            # Match timestamp
            # Convert time column to string to compare
            df_sym['time_str'] = df_sym['time'].astype(str)
            mask = df_sym['time_str'] == str(sell_time)
            rows = df_sym[mask]
            
            if not rows.empty:
                regime = rows.iloc[0]['regime']
            else:
                # Fallback to closest match
                regime = "QUIET_RANGING"
        else:
            regime = "QUIET_RANGING"
            
        if regime in regime_pnl:
            regime_pnl[regime].append(pnl)
            regime_counts[regime] += 1
            if pnl > 0:
                regime_win_counts[regime] += 1

    # Summarize stats
    regime_summary = {}
    for r in regime_pnl.keys():
        pnls = regime_pnl[r]
        total_r_pnl = sum(pnls)
        avg_r_pnl = np.mean(pnls) if pnls else 0.0
        win_rate = regime_win_counts[r] / regime_counts[r] if regime_counts[r] > 0 else 0.0
        
        regime_summary[r] = {
            "trade_count": regime_counts[r],
            "total_pnl": float(total_r_pnl),
            "avg_pnl": float(avg_r_pnl),
            "win_rate": float(win_rate),
            "trades": pnls
        }

    # Also compute overall market regime representation (percentage of bars)
    regime_bar_distribution = {k: 0.0 for k in regime_pnl.keys()}
    total_bars = 0
    for sym, df in classified_dfs.items():
        counts = df['regime'].value_counts()
        for k, v in counts.items():
            if k in regime_bar_distribution:
                regime_bar_distribution[k] += v
                total_bars += v

    if total_bars > 0:
        for k in regime_bar_distribution.keys():
            regime_bar_distribution[k] = float(regime_bar_distribution[k] / total_bars)

    return {
        "regime_attribution": regime_summary,
        "market_regime_distribution": regime_bar_distribution
    }
