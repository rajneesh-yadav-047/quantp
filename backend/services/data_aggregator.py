"""
Universal Data Aggregator for SmartAPI historical data.

Downloads large date ranges in chunks (respecting Angel One API limits),
merges the results, validates completeness, fills gaps, and ensures
correct interval continuity across all timeframes.

Usage:
    df = aggregate_data(symbol, interval, start_date, end_date, client)
    # df is a validated, gap-filled, contiguous DataFrame

Can be used by backtest, multi-asset research, dataset analysis, etc.
"""

import time
import math
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List, Dict, Any
import pandas as pd
import numpy as np

from backend.smartapi import SmartAPIClient


# ────────────────────── Angel One API chunk limits ──────────────────────
# Determined from SmartAPI docs + empirical testing
_CHUNK_LIMITS: Dict[str, int] = {
    "ONE_MINUTE": 30,         # 30 days max per request
    "FIVE_MINUTE": 60,        # 60 days
    "FIFTEEN_MINUTE": 60,     # 60 days
    "THIRTY_MINUTE": 60,      # 60 days
    "ONE_HOUR": 120,          # 120 days
    "ONE_DAY": 2000,          # ~2000 days (~5.5 years)
    "ONE_WEEK": 2000,         # ~same as daily effectively
    "ONE_MONTH": 2000,
}

# Interval minutes mapping for validation
_INTERVAL_MINUTES: Dict[str, int] = {
    "ONE_MINUTE": 1,
    "FIVE_MINUTE": 5,
    "FIFTEEN_MINUTE": 15,
    "THIRTY_MINUTE": 30,
    "ONE_HOUR": 60,
    "ONE_DAY": 375,         # 9:15 to 15:30 = 375 minutes (used for gap detection logic)
    "ONE_WEEK": 7 * 24 * 60,
    "ONE_MONTH": 30 * 24 * 60,
}


# ────────────────────── Date helpers ──────────────────────

def _parse_date_str(date_str: str) -> datetime:
    """Parse flexible date string into datetime."""
    s = date_str.strip()
    if len(s) <= 10:
        return pd.to_datetime(s, format="%Y-%m-%d", errors="raise").to_pydatetime()
    return pd.to_datetime(s).to_pydatetime()


def _to_date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def _trading_dates_between(start: date, end: date) -> List[date]:
    """Return all trading dates (Mon-Fri) between start and end inclusive."""
    dates = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            dates.append(cur)
        cur += timedelta(days=1)
    return dates


def _chunk_size_days(interval: str) -> int:
    return _CHUNK_LIMITS.get(interval.upper(), 60)


def _interval_minutes(interval: str) -> int:
    return _INTERVAL_MINUTES.get(interval.upper(), 1)


# ────────────────────── Core Aggregator ──────────────────────

def aggregate_data(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    client: Optional[SmartAPIClient] = None,
    max_retries: int = 3,
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Download and aggregate historical candle data across a large date range.

    Breaks the request into API-safe chunks, merges them, deduplicates,
    validates interval continuity, and fills any gaps (with a warning).

    Returns:
        (df, status)
        - df: Validated, gap-filled DataFrame with columns [time, open, high, low, close, volume, open_interest]
        - status: "ok" | "partial" (some gaps filled) | "failed" (no data returned) | "mock" (data was mock)
    """
    client = client or SmartAPIClient()
    interval = interval.upper()
    chunk_days = _chunk_size_days(interval)

    start_dt = _parse_date_str(start_date)
    end_dt = _parse_date_str(end_date)

    # Ensure market hours for SmartAPI from/to
    chunk_start = start_dt
    chunks: List[pd.DataFrame] = []
    any_mock = False

    while chunk_start <= end_dt:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_dt)

        from_str = f"{_to_date_str(chunk_start)} 09:15"
        to_str = f"{_to_date_str(chunk_end)} 15:30"

        df_chunk, is_mock = _fetch_with_retry(
            client, symbol, from_str, to_str, interval, max_retries
        )

        if is_mock:
            any_mock = True
            # If mock was returned, we stop — user wants real data only
            print(f"WARN: Mock data returned for {symbol} {interval}. Aborting chunk download.")
            break

        if df_chunk is not None and not df_chunk.empty:
            chunks.append(df_chunk)

        chunk_start = chunk_end + timedelta(days=1)
        # Rate-limit padding between chunks
        time.sleep(0.3)

    if not chunks:
        return None, "failed"

    # ── Merge chunks ──
    merged = _merge_chunks(chunks)
    if merged is None or merged.empty:
        return None, "failed"

    # ── Slice to exact requested range ──
    merged = _slice_exact_range(merged, start_dt, end_dt)
    if merged is None or merged.empty:
        return None, "failed"

    # ── Validate & fill gaps ──
    merged, gaps_info = _validate_and_fill(merged, interval)

    status = "ok" if not gaps_info else "partial"
    if any_mock:
        status = "mock"

    return merged, status


def _fetch_with_retry(
    client: SmartAPIClient,
    symbol: str,
    from_date: str,
    to_date: str,
    interval: str,
    max_retries: int,
) -> Tuple[Optional[pd.DataFrame], bool]:
    """Fetch a single chunk with retry logic."""
    for attempt in range(max_retries):
        try:
            df, is_mock = client.fetch_historical_candles(symbol, from_date, to_date, interval)
            if is_mock:
                return df, True
            if df is not None and not df.empty:
                return df, False
        except Exception as e:
            print(f"WARN: Chunk fetch attempt {attempt + 1}/{max_retries} failed for {symbol} {from_date}–{to_date}: {e}")
        if attempt < max_retries - 1:
            time.sleep(0.5 * (attempt + 1))
    return None, False


def _merge_chunks(chunks: List[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate chunks, deduplicate by time, sort by time."""
    combined = pd.concat(chunks, ignore_index=True)
    # Ensure time column exists and is parsed
    if "time" not in combined.columns:
        return None

    combined["time"] = pd.to_datetime(combined["time"], errors="coerce")
    combined = combined.dropna(subset=["time"])
    combined = combined.sort_values("time")

    # Deduplicate on exact timestamp (keep last = most recent download)
    combined = combined.drop_duplicates(subset=["time"], keep="last")
    combined = combined.reset_index(drop=True)
    return combined


def _slice_exact_range(
    df: pd.DataFrame,
    start_dt: datetime,
    end_dt: datetime,
) -> pd.DataFrame:
    """Slice DataFrame to exact requested datetime range."""
    if df["time"].dt.tz is not None:
        df["time"] = df["time"].dt.tz_localize(None)
    mask = (df["time"] >= start_dt) & (df["time"] <= end_dt + timedelta(hours=23, minutes=59, seconds=59))
    return df.loc[mask].copy()


def _validate_and_fill(
    df: pd.DataFrame,
    interval: str,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate that all expected time intervals are present.
    Detect gaps and fill them using forward-fill / backward-fill of OHLCV.

    Returns:
        (filled_df, gap_messages)
    """
    interval = interval.upper()
    gaps_info: List[str] = []

    if df.empty:
        return df, gaps_info

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)

    # Ensure numeric columns
    numeric_cols = ["open", "high", "low", "close", "volume", "open_interest"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = 0.0 if col != "volume" else 0
    # Default open_interest if missing
    if "open_interest" not in df.columns:
        df["open_interest"] = 0

    if interval in ("ONE_DAY", "ONE_WEEK", "ONE_MONTH"):
        # Daily/weekly/monthly: just check trading-day gaps, fill simply
        df, gaps_info = _fill_daily_gaps(df, interval)
    else:
        # Intraday: need to respect market hours (9:15–15:30 IST)
        df, gaps_info = _fill_intraday_gaps(df, interval)

    return df, gaps_info


def _fill_daily_gaps(df: pd.DataFrame, interval: str) -> Tuple[pd.DataFrame, List[str]]:
    """Fill gaps for daily/weekly/monthly data."""
    gaps_info: List[str] = []
    if df.empty:
        return df, gaps_info

    start_date = df["time"].min().date()
    end_date = df["time"].max().date()

    trading_dates = _trading_dates_between(start_date, end_date)
    expected_times = pd.to_datetime(trading_dates)

    # Reindex to expected trading days
    df_indexed = df.set_index("time")
    df_reindexed = df_indexed.reindex(expected_times)

    # Detect gaps
    missing_mask = df_reindexed["close"].isna()
    if missing_mask.any():
        gap_dates = df_reindexed.index[missing_mask].strftime("%Y-%m-%d").tolist()
        gaps_info.append(f"Missing {missing_mask.sum()} daily bars: {gap_dates[:5]}{'...' if len(gap_dates) > 5 else ''}")

    # Fill OHLC with previous close, volume=0, open_interest=0
    df_reindexed["close"] = df_reindexed["close"].ffill().bfill()
    df_reindexed["open"] = df_reindexed["open"].fillna(df_reindexed["close"])
    df_reindexed["high"] = df_reindexed["high"].fillna(df_reindexed["close"])
    df_reindexed["low"] = df_reindexed["low"].fillna(df_reindexed["close"])
    df_reindexed["volume"] = df_reindexed["volume"].fillna(0).astype(int)
    df_reindexed["open_interest"] = df_reindexed["open_interest"].fillna(0).astype(int)

    df_filled = df_reindexed.reset_index().rename(columns={"index": "time"})
    df_filled = df_filled.dropna(subset=["time"])
    return df_filled, gaps_info


def _fill_intraday_gaps(df: pd.DataFrame, interval: str) -> Tuple[pd.DataFrame, List[str]]:
    """
    Fill gaps for intraday data (1m, 5m, 15m, 30m, 1h).

    Respects Indian market hours: 9:15 AM to 3:30 PM IST.
    Only generates expected bars during trading hours, Mon-Fri.
    """
    gaps_info: List[str] = []
    if df.empty:
        return df, gaps_info

    step_mins = _interval_minutes(interval)
    if step_mins <= 0:
        step_mins = 5

    start_dt = df["time"].min()
    end_dt = df["time"].max()

    expected_times = _generate_intraday_times(start_dt, end_dt, step_mins)
    if len(expected_times) == 0:
        return df, gaps_info

    df_indexed = df.set_index("time")
    df_reindexed = df_indexed.reindex(expected_times)

    missing_mask = df_reindexed["close"].isna()
    if missing_mask.any():
        gap_count = int(missing_mask.sum())
        # Show first gap detail
        first_gap = df_reindexed.index[missing_mask][0] if gap_count > 0 else None
        gaps_info.append(
            f"Missing {gap_count} {interval} bars. "
            f"First gap: {first_gap}. Filled with forward-fill."
        )

    # Fill OHLC from previous close
    df_reindexed["close"] = df_reindexed["close"].ffill().bfill()
    df_reindexed["open"] = df_reindexed["open"].fillna(df_reindexed["close"])
    df_reindexed["high"] = df_reindexed["high"].fillna(df_reindexed["close"])
    df_reindexed["low"] = df_reindexed["low"].fillna(df_reindexed["close"])
    df_reindexed["volume"] = df_reindexed["volume"].fillna(0).astype(int)
    df_reindexed["open_interest"] = df_reindexed["open_interest"].fillna(0).astype(int)

    df_filled = df_reindexed.reset_index().rename(columns={"index": "time"})
    df_filled = df_filled.dropna(subset=["time"])
    return df_filled, gaps_info


def _generate_intraday_times(start: datetime, end: datetime, step_mins: int) -> pd.DatetimeIndex:
    """
    Generate all expected intraday timestamps respecting Indian market hours.
    Market: 09:15 to 15:30 IST, Mon-Fri.
    """
    # Assume data is already in local IST (no timezone conversion needed for validation)
    times = []
    cur_date = start.date()
    end_date = end.date()

    while cur_date <= end_date:
        if cur_date.weekday() >= 5:
            cur_date += timedelta(days=1)
            continue

        day_start = datetime.combine(cur_date, datetime.min.time()) + timedelta(hours=9, minutes=15)
        day_end = datetime.combine(cur_date, datetime.min.time()) + timedelta(hours=15, minutes=30)

        # Clamp to actual range
        effective_start = max(day_start, start) if cur_date == start.date() else day_start
        effective_end = min(day_end, end) if cur_date == end_date else day_end

        if effective_start <= effective_end:
            t = effective_start
            while t <= effective_end:
                times.append(t)
                t += timedelta(minutes=step_mins)

        cur_date += timedelta(days=1)

    return pd.DatetimeIndex(times)


# ────────────────────── Convenience: save aggregated data ──────────────────────

def aggregate_and_save(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    client: Optional[SmartAPIClient] = None,
) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
    """
    Aggregate data and save to CSV catalog.

    Returns:
        (df, status, file_path)
    """
    client = client or SmartAPIClient()
    df, status = aggregate_data(symbol, interval, start_date, end_date, client)
    if df is None or df.empty:
        return None, status, None
    if status == "mock":
        return df, status, None

    file_path = client.save_dataset_csv(symbol, interval, df, is_mock=False)
    return df, status, file_path


# ────────────────────── Interval validation helper ──────────────────────

def get_interval_metadata(df: pd.DataFrame, interval: str) -> Dict[str, Any]:
    """
    Return diagnostic metadata about the aggregated dataset.
    Useful for front-end or back-end logging.
    """
    if df is None or df.empty:
        return {
            "interval": interval,
            "records": 0,
            "start": None,
            "end": None,
            "gaps": 0,
            "expected_bars": 0,
            "coverage_pct": 0.0,
        }

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")

    start = df["time"].min()
    end = df["time"].max()
    records = len(df)

    if interval.upper() in ("ONE_DAY", "ONE_WEEK", "ONE_MONTH"):
        expected_bars = len(_trading_dates_between(start.date(), end.date()))
    else:
        step_mins = _interval_minutes(interval)
        expected_times = _generate_intraday_times(start.to_pydatetime(), end.to_pydatetime(), step_mins)
        expected_bars = len(expected_times)

    gaps = max(0, expected_bars - records)
    coverage_pct = round((records / expected_bars) * 100, 2) if expected_bars > 0 else 0.0

    return {
        "interval": interval,
        "records": records,
        "start": str(start),
        "end": str(end),
        "gaps": gaps,
        "expected_bars": expected_bars,
        "coverage_pct": coverage_pct,
    }
