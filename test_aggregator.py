"""
Test the universal data aggregator's core logic without needing SmartAPI credentials.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
from datetime import datetime, timedelta
from backend.services.data_aggregator import (
    _merge_chunks,
    _fill_daily_gaps,
    _fill_intraday_gaps,
    _validate_and_fill,
    _chunk_size_days,
    _interval_minutes,
    _generate_intraday_times,
    get_interval_metadata,
)


def test_chunk_size_days():
    assert _chunk_size_days("ONE_MINUTE") == 30
    assert _chunk_size_days("FIVE_MINUTE") == 60
    assert _chunk_size_days("ONE_HOUR") == 120
    assert _chunk_size_days("ONE_DAY") == 2000
    print("✅ test_chunk_size_days passed")


def test_interval_minutes():
    assert _interval_minutes("ONE_MINUTE") == 1
    assert _interval_minutes("FIVE_MINUTE") == 5
    assert _interval_minutes("ONE_HOUR") == 60
    assert _interval_minutes("ONE_DAY") == 375
    print("✅ test_interval_minutes passed")


def test_merge_chunks():
    chunk1 = pd.DataFrame({
        "time": ["2024-01-01 09:15:00", "2024-01-01 09:16:00", "2024-01-01 09:17:00"],
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 1100, 1200],
        "open_interest": [0, 0, 0],
    })
    chunk2 = pd.DataFrame({
        "time": ["2024-01-01 09:17:00", "2024-01-01 09:18:00", "2024-01-01 09:19:00"],  # 09:17 duplicated
        "open": [102, 103, 104],
        "high": [103, 104, 105],
        "low": [101, 102, 103],
        "close": [103, 104, 105],
        "volume": [1200, 1300, 1400],
        "open_interest": [0, 0, 0],
    })
    merged = _merge_chunks([chunk1, chunk2])
    assert len(merged) == 5, f"Expected 5 rows after dedup (3+3-1), got {len(merged)}"
    assert list(merged["time"]) == [
        pd.Timestamp("2024-01-01 09:15:00"),
        pd.Timestamp("2024-01-01 09:16:00"),
        pd.Timestamp("2024-01-01 09:17:00"),
        pd.Timestamp("2024-01-01 09:18:00"),
        pd.Timestamp("2024-01-01 09:19:00"),
    ]
    # The duplicate 09:17 should keep the LAST value (from chunk2, close=103)
    assert merged[merged["time"] == "2024-01-01 09:17:00"]["close"].iloc[0] == 103
    print("✅ test_merge_chunks passed")


def test_fill_daily_gaps():
    # Monday, Tuesday, Thursday (missing Wednesday)
    df = pd.DataFrame({
        "time": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-04"]),  # Mon, Tue, Thu
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 1100, 1200],
        "open_interest": [0, 0, 0],
    })
    filled, gaps = _fill_daily_gaps(df, "ONE_DAY")
    assert len(filled) == 4, f"Expected 4 rows (Mon-Thu), got {len(filled)}"
    assert len(gaps) == 1, f"Expected 1 gap message, got {len(gaps)}"
    # Wednesday should be filled with Tuesday's close=102
    wed_row = filled[filled["time"] == pd.Timestamp("2024-01-03")]
    assert len(wed_row) == 1
    assert wed_row["close"].iloc[0] == 102
    assert wed_row["volume"].iloc[0] == 0
    print("✅ test_fill_daily_gaps passed")


def test_fill_intraday_gaps():
    # 5-minute interval: 9:15, 9:20, 9:30 (missing 9:25)
    df = pd.DataFrame({
        "time": pd.to_datetime(["2024-01-01 09:15:00", "2024-01-01 09:20:00", "2024-01-01 09:30:00"]),
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 1100, 1200],
        "open_interest": [0, 0, 0],
    })
    filled, gaps = _fill_intraday_gaps(df, "FIVE_MINUTE")
    # Market: 9:15 to 9:30 = 4 bars (9:15, 9:20, 9:25, 9:30)
    assert len(filled) == 4, f"Expected 4 rows, got {len(filled)}"
    assert len(gaps) == 1, f"Expected 1 gap message, got {len(gaps)}"
    # 9:25 should be filled with forward fill from 9:20 close=102
    gap_row = filled[filled["time"] == pd.Timestamp("2024-01-01 09:25:00")]
    assert len(gap_row) == 1
    assert gap_row["close"].iloc[0] == 102
    assert gap_row["volume"].iloc[0] == 0
    print("✅ test_fill_intraday_gaps passed")


def test_generate_intraday_times():
    start = datetime(2024, 1, 1, 9, 15)
    end = datetime(2024, 1, 1, 9, 30)
    times = _generate_intraday_times(start, end, 5)
    expected = [
        datetime(2024, 1, 1, 9, 15),
        datetime(2024, 1, 1, 9, 20),
        datetime(2024, 1, 1, 9, 25),
        datetime(2024, 1, 1, 9, 30),
    ]
    assert list(times) == expected, f"Expected {expected}, got {list(times)}"
    print("✅ test_generate_intraday_times passed")


def test_validate_and_fill_daily():
    df = pd.DataFrame({
        "time": ["2024-01-01", "2024-01-02", "2024-01-04"],
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 1100, 1200],
        "open_interest": [0, 0, 0],
    })
    filled, gaps = _validate_and_fill(df, "ONE_DAY")
    assert len(filled) == 4
    assert len(gaps) == 1
    print("✅ test_validate_and_fill_daily passed")


def test_validate_and_fill_intraday():
    df = pd.DataFrame({
        "time": ["2024-01-01 09:15:00", "2024-01-01 09:20:00", "2024-01-01 09:30:00"],
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 1100, 1200],
        "open_interest": [0, 0, 0],
    })
    filled, gaps = _validate_and_fill(df, "FIVE_MINUTE")
    assert len(filled) == 4
    assert len(gaps) == 1
    print("✅ test_validate_and_fill_intraday passed")


def test_get_interval_metadata():
    df = pd.DataFrame({
        "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 1100, 1200],
        "open_interest": [0, 0, 0],
    })
    meta = get_interval_metadata(df, "ONE_DAY")
    assert meta["records"] == 3
    assert meta["expected_bars"] == 3
    assert meta["gaps"] == 0
    assert meta["coverage_pct"] == 100.0
    print("✅ test_get_interval_metadata passed")


if __name__ == "__main__":
    test_chunk_size_days()
    test_interval_minutes()
    test_merge_chunks()
    test_fill_daily_gaps()
    test_fill_intraday_gaps()
    test_generate_intraday_times()
    test_validate_and_fill_daily()
    test_validate_and_fill_intraday()
    test_get_interval_metadata()
    print("\n🎉 All aggregator tests passed!")
