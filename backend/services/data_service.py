"""
Data service: shared data loading, date slicing, and mock generation.

Centralizes all data preparation logic that was previously duplicated
across backtest, research, and capital endpoints.
"""

import time
from typing import Dict, Optional, Tuple
import pandas as pd
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager


def parse_date_range(start_date: str, end_date: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Parse and validate date strings into pandas Timestamps.
    
    Args:
        start_date: YYYY-MM-DD or flexible format
        end_date: YYYY-MM-DD or flexible format
        
    Returns:
        (start_dt, end_dt) where end_dt includes full day if no time provided
        
    Raises:
        ValueError: if dates are unparseable
    """
    def _parse(dt_str: str) -> pd.Timestamp:
        s = dt_str.strip()
        # Try ISO format first (handles "2026-06-01T09:15:00+05:30")
        try:
            return pd.to_datetime(s, format='ISO8601')
        except Exception:
            pass
        # Try standard YYYY-MM-DD
        try:
            return pd.to_datetime(s, format='%Y-%m-%d', errors='raise')
        except Exception:
            pass
        # Fallback — but force year-first to avoid dayfirst misinterpretation
        result = pd.to_datetime(s, dayfirst=False, errors='coerce')
        if pd.isna(result):
            raise ValueError(f"Invalid date format: '{dt_str}'. Expected YYYY-MM-DD or ISO8601.")
        return result
    
    start_dt = _parse(start_date)
    end_dt = _parse(end_date)
    
    # Strip timezone info for consistent comparison
    if start_dt.tz is not None:
        start_dt = start_dt.tz_localize(None)
    if end_dt.tz is not None:
        end_dt = end_dt.tz_localize(None)
    
    if len(end_date.strip()) <= 10:
        end_dt = end_dt + pd.Timedelta(hours=23, minutes=59, seconds=59)
    
    return start_dt, end_dt


def slice_dataframe_by_date(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    time_col: str = "time",
) -> pd.DataFrame:
    """
    Slice a DataFrame by date range, handling timezone stripping.
    
    Args:
        df: DataFrame with time_col
        start_date: start date string
        end_date: end date string
        time_col: name of the time column
        
    Returns:
        Sliced DataFrame with time_col kept as-is (time_dt dropped)
    """
    start_dt, end_dt = parse_date_range(start_date, end_date)
    
    time_series = pd.to_datetime(df[time_col])
    if time_series.dt.tz is not None:
        df['time_dt'] = time_series.dt.tz_localize(None)
    else:
        df['time_dt'] = time_series
    
    df = df[(df['time_dt'] >= start_dt) & (df['time_dt'] <= end_dt)]
    df = df.ffill().bfill()
    
    if 'time_dt' in df.columns:
        df = df.drop(columns=['time_dt'])
    
    return df


def normalize_symbol(symbol: str, interval: str, client: Optional[SmartAPIClient] = None) -> str:
    """
    Normalize a bare symbol to its canonical exchange-prefixed form.
    
    Examples:
      - 'AEGISLOG' -> 'NSE:AEGISLOG-EQ' (if found in catalog or token list)
      - 'NSE:AEGISLOG-EQ' -> 'NSE:AEGISLOG-EQ' (already canonical, passthrough)
      - 'SBIN' -> 'NSE:SBIN-EQ'
      
    Args:
        symbol: raw symbol input (may or may not have exchange prefix)
        interval: candle interval (used for catalog lookups)
        client: optional SmartAPIClient for token resolution
        
    Returns:
        Canonical symbol string best matching the input.
    """
    sym = symbol.upper().strip()
    
    # Already canonical — passthrough
    if ":" in sym:
        return sym
    
    catalog_client = client or SmartAPIClient()
    catalog = catalog_client.load_catalog()
    
    # 1. Check catalog for canonical NSE equity form FIRST (prefer real data)
    canonical_eq = f"NSE:{sym}-EQ"
    eq_key = f"{canonical_eq}_{interval.upper()}"
    if eq_key in catalog:
        return canonical_eq
    
    # 2. Check catalog for exact bare key (backward compat)
    exact_key = f"{sym}_{interval.upper()}"
    if exact_key in catalog:
        return sym  # catalog has this exact bare symbol, trust it
    
    # 3. Check catalog for any exchange-prefixed version of this symbol
    for key, entry in catalog.items():
        cat_symbol = entry.get("symbol", "")
        if cat_symbol.upper() == sym:
            return cat_symbol
        if ":" in cat_symbol:
            _, cat_base = cat_symbol.split(":", 1)
            if cat_base.upper() == sym:
                return cat_symbol
    
    # 4. Try SmartAPI token resolution for NSE equity default
    try:
        token_client = client or SmartAPIClient()
        resolved = token_client.resolve_symbol(f"NSE:{sym}")
        if resolved:
            exch = resolved.get("exch_seg", "NSE")
            resolved_symbol = resolved.get("symbol", sym)
            return f"{exch}:{resolved_symbol}"
    except Exception as e:
        print(f"WARN: Symbol normalization failed for {sym}: {e}")
    
    # 5. Fallback: assume NSE equity
    return f"NSE:{sym}-EQ"


def load_or_download_symbol_data(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    auto_download: bool = True,
    client: Optional[SmartAPIClient] = None,
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Load dataset from catalog, or download if missing and auto_download is True.
    
    Args:
        symbol: instrument symbol
        interval: candle interval
        start_date: backtest start date
        end_date: backtest end date
        auto_download: whether to fetch missing data from SmartAPI
        client: optional shared download client
        
    Returns:
        (DataFrame or None, status_message)
        status_message: "loaded", "downloaded", "mock", or "failed"
    """
    sym = symbol.upper().strip()
    # Normalize bare symbols (e.g. "AEGISLOG" -> "NSE:AEGISLOG-EQ")
    normalized_sym = normalize_symbol(sym, interval, client)
    catalog_client = SmartAPIClient()
    df = catalog_client.load_dataset_csv(normalized_sym, interval)
    
    # Auto-download if missing
    if (df is None or df.empty) and auto_download and client is not None:
        try:
            df, is_mock = client.fetch_historical_candles(
                symbol=normalized_sym,
                from_date=f"{start_date} 09:15",
                to_date=f"{end_date} 15:30",
                interval=interval,
            )
            if is_mock:
                print(f"WARN: Symbol {normalized_sym} not found on SmartAPI. Skipping mock data save.")
                return None, "failed"
            if not df.empty:
                client.save_dataset_csv(normalized_sym, interval, df)
                time.sleep(0.5)  # rate limit padding
                return df, "downloaded"
        except Exception as e:
            print(f"WARN: Auto-download failed for {normalized_sym}: {e}")
    
    # Do NOT generate mock data as fallback - require real data only
    if df is None or df.empty:
        return None, "failed"
    
    if df is None or df.empty:
        return None, "failed"
    
    return df, "loaded"


def prepare_backtest_data(
    symbols: list,
    interval: str,
    start_date: str,
    end_date: str,
    auto_download: bool = True,
) -> Tuple[Dict[str, pd.DataFrame], list, list]:
    """
    Prepare DataFrames for all symbols needed in a backtest.
    
    Args:
        symbols: list of symbol strings
        interval: candle interval
        start_date: backtest start
        end_date: backtest end
        auto_download: whether to auto-download missing data
        
    Returns:
        (df_dict, downloaded_symbols, failed_symbols)
    """
    df_dict: Dict[str, pd.DataFrame] = {}
    downloaded_symbols: list = []
    failed_symbols: list = []
    
    # Prepare shared download client
    dl_client: Optional[SmartAPIClient] = None
    if auto_download and SmartAPIManager.is_configured():
        dl_client = SmartAPIManager.create_fresh_client()
        if not dl_client.connect():
            print(f"WARN: Shared SmartAPI connect failed: {dl_client.last_error}")
            dl_client = None
    
    for symbol in symbols:
        sym = symbol.upper().strip()
        if not sym:
            continue
        
        # Normalize to canonical form for consistent catalog lookup
        normalized_sym = normalize_symbol(sym, interval, dl_client)
        
        df, status = load_or_download_symbol_data(
            symbol=normalized_sym,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            auto_download=auto_download,
            client=dl_client,
        )
        
        if status == "downloaded":
            downloaded_symbols.append(normalized_sym)
        elif status == "mock":
            downloaded_symbols.append(f"{normalized_sym}(mock)")
        elif status == "failed":
            failed_symbols.append(normalized_sym)
            continue
        
        # Slice to requested date range
        try:
            df = slice_dataframe_by_date(df, start_date, end_date)
        except Exception as e:
            failed_symbols.append(f"{normalized_sym} (date slice error: {e})")
            continue
        
        if not df.empty:
            df_dict[normalized_sym] = df
    
    return df_dict, downloaded_symbols, failed_symbols
