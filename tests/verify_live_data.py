"""
Live Data Verification Test
============================
Fetches live/real data from SmartAPI and compares the last candle values
against the locally stored CSV dataset to confirm data correctness.

Usage:
    .venv/Scripts/python tests/verify_live_data.py --symbol SBIN --interval ONE_MINUTE --totp 123456
    .venv/Scripts/python tests/verify_live_data.py --symbol IN --interval FIVE_MINUTE --totp 123456
    .venv/Scripts/python tests/verify_live_data.py --all --totp 123456

Output:
    - Prints side-by-side comparison of last candle values
    - Reports MATCH or MISMATCH for each field
    - Exit code 0 if all match, 1 if any mismatch
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager


def format_candle(candle: dict) -> str:
    """Pretty-print a single candle dict."""
    return (
        f"time={candle.get('time', 'N/A')}, "
        f"open={candle.get('open', 'N/A')}, "
        f"high={candle.get('high', 'N/A')}, "
        f"low={candle.get('low', 'N/A')}, "
        f"close={candle.get('close', 'N/A')}, "
        f"volume={candle.get('volume', 'N/A')}"
    )


def verify_symbol(symbol: str, interval: str, totp: str, tolerance: float = 0.01) -> dict:
    """
    Fetch live data from SmartAPI and compare the last candle with stored CSV.

    Returns dict with keys:
        - symbol, interval
        - stored_last: dict with last candle from CSV
        - live_last: dict with last candle from SmartAPI
        - match: bool overall
        - field_results: dict of per-field comparison
        - error: str or None
    """
    result = {
        "symbol": symbol,
        "interval": interval,
        "stored_last": None,
        "live_last": None,
        "match": False,
        "field_results": {},
        "error": None,
    }

    # 1. Load stored CSV
    catalog_path = "./datasets/catalog.json"
    if not os.path.exists(catalog_path):
        result["error"] = "catalog.json not found"
        return result

    with open(catalog_path, "r") as f:
        catalog = json.load(f)

    key = f"{symbol.upper()}_{interval.upper()}"
    meta = catalog.get(key)
    if not meta:
        result["error"] = f"{key} not found in catalog"
        return result

    file_path = meta.get("file_path")
    if not file_path or not os.path.exists(file_path):
        result["error"] = f"Stored file missing: {file_path}"
        return result

    try:
        if file_path.endswith(".xlsx"):
            stored_df = pd.read_excel(file_path, engine="openpyxl")
        else:
            stored_df = pd.read_csv(file_path)
    except Exception as e:
        result["error"] = f"Failed to read stored file: {e}"
        return result

    if stored_df.empty:
        result["error"] = "Stored dataset is empty"
        return result

    stored_last = stored_df.iloc[-1].to_dict()
    result["stored_last"] = stored_last

    # 2. Determine the date range for live fetch
    # We fetch the last day of stored data to compare the overlapping candles
    last_time_str = str(stored_last.get("time", ""))
    try:
        # Try to parse the time - it can be ISO format or simple YYYY-MM-DD HH:MM:SS
        last_time = pd.to_datetime(last_time_str).tz_localize(None)
    except Exception:
        result["error"] = f"Cannot parse stored last time: {last_time_str}"
        return result

    # Fetch from the start of the last stored day up to the last stored time + 1 day
    from_date = last_time.strftime("%Y-%m-%d") + " 09:15"
    to_date = (last_time + timedelta(days=1)).strftime("%Y-%m-%d") + " 15:30"

    # 3. Fetch live data from SmartAPI
    client = SmartAPIManager.get_client()
    if not client:
        client = SmartAPIClient()

    if not client.is_configured():
        result["error"] = "SmartAPI credentials not configured in .env"
        return result

    connected = False
    if client.jwt_token:
        connected = True
    else:
        connected = client.connect(totp=totp)
        if connected:
            SmartAPIManager.set_client(client)

    if not connected:
        result["error"] = f"SmartAPI connection failed: {client.last_error}"
        return result

    try:
        live_df = client.fetch_historical_candles(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
        )
    except Exception as e:
        result["error"] = f"SmartAPI fetch failed: {e}"
        return result

    if live_df is None or live_df.empty:
        result["error"] = "SmartAPI returned empty data (may be mock fallback)"
        return result

    # Check if the data came from SmartAPI or mock generator
    is_mock = not bool(client.jwt_token and client.is_configured())
    if is_mock:
        result["error"] = "Data is from mock generator, not live SmartAPI"
        return result

    live_last = live_df.iloc[-1].to_dict()
    result["live_last"] = live_last

    # 4. Compare the last candles
    # Normalize types for comparison
    numeric_fields = ["open", "high", "low", "close", "volume"]
    for field in numeric_fields:
        stored_val = stored_last.get(field)
        live_val = live_last.get(field)

        try:
            stored_num = float(stored_val) if stored_val is not None else None
            live_num = float(live_val) if live_val is not None else None
        except (ValueError, TypeError):
            result["field_results"][field] = {
                "match": False,
                "stored": stored_val,
                "live": live_val,
                "reason": "non-numeric value",
            }
            continue

        if stored_num is None or live_num is None:
            result["field_results"][field] = {
                "match": False,
                "stored": stored_val,
                "live": live_val,
                "reason": "missing value",
            }
            continue

        # For price fields, use relative tolerance
        if field in ["open", "high", "low", "close"]:
            if stored_num == 0:
                match = abs(live_num) < tolerance
            else:
                match = abs((live_num - stored_num) / stored_num) < tolerance
        else:
            # For volume, use absolute tolerance (can be large differences)
            match = abs(live_num - stored_num) <= max(1, abs(stored_num) * 0.05)

        result["field_results"][field] = {
            "match": match,
            "stored": stored_num,
            "live": live_num,
            "diff": round(live_num - stored_num, 4),
            "diff_pct": round((live_num - stored_num) / stored_num * 100, 4) if stored_num != 0 else None,
        }

    result["match"] = all(
        r.get("match", False) for r in result["field_results"].values()
    )
    return result


def print_result(result: dict, verbose: bool = True):
    """Print a single verification result in a readable format."""
    symbol = result["symbol"]
    interval = result["interval"]
    error = result["error"]

    print(f"\n{'='*60}")
    print(f"  VERIFICATION: {symbol} | {interval}")
    print(f"{'='*60}")

    if error:
        print(f"  [ERROR] {error}")
        return

    stored = result["stored_last"]
    live = result["live_last"]

    print(f"  Stored last candle:")
    print(f"    {format_candle(stored)}")
    print(f"  Live last candle:")
    print(f"    {format_candle(live)}")
    print(f"  {'-'*56}")
    print(f"  {'Field':<12} {'Stored':>14} {'Live':>14} {'Diff':>14} {'Match':>8}")
    print(f"  {'-'*56}")

    for field, info in result["field_results"].items():
        if info["match"]:
            match_str = "PASS"
        else:
            match_str = "FAIL"

        diff_str = ""
        if "diff" in info:
            diff_str = f"{info['diff']:+.4f}"
        elif "reason" in info:
            diff_str = info["reason"]

        print(
            f"  {field:<12} "
            f"{info.get('stored', 'N/A'):>14} "
            f"{info.get('live', 'N/A'):>14} "
            f"{diff_str:>14} "
            f"{match_str:>8}"
        )

    print(f"  {'-'*56}")
    if result["match"]:
        print(f"  RESULT: [PASS] All fields match within tolerance")
    else:
        print(f"  RESULT: [FAIL] Mismatch detected - data may be stale or corrupted")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Verify stored CSV data against live SmartAPI feed")
    parser.add_argument("--symbol", type=str, help="Symbol to verify (e.g. SBIN)")
    parser.add_argument("--interval", type=str, default="ONE_MINUTE", help="Interval (e.g. ONE_MINUTE, FIVE_MINUTE)")
    parser.add_argument("--totp", type=str, required=True, help="6-digit TOTP code for SmartAPI auth")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Price comparison tolerance (default 1%%)")
    parser.add_argument("--all", action="store_true", help="Verify all datasets in catalog")
    args = parser.parse_args()

    if not args.all and not args.symbol:
        print("[ERROR] Provide --symbol or use --all")
        sys.exit(1)

    # Load catalog to get target list
    catalog_path = "./datasets/catalog.json"
    if not os.path.exists(catalog_path):
        print("[ERROR] catalog.json not found")
        sys.exit(1)

    with open(catalog_path, "r") as f:
        catalog = json.load(f)

    targets = []
    if args.all:
        for key, meta in catalog.items():
            sym = meta.get("symbol", "").upper()
            iv = meta.get("interval", "").upper()
            if sym and iv:
                targets.append((sym, iv))
    else:
        targets = [(args.symbol.upper(), args.interval.upper())]

    if not targets:
        print("[ERROR] No targets to verify")
        sys.exit(1)

    results = []
    for sym, iv in targets:
        # Skip test entries
        if sym == "TEST":
            print(f"[SKIP] Skipping test entry {sym}_{iv}")
            continue
        res = verify_symbol(sym, iv, args.totp, args.tolerance)
        print_result(res)
        results.append(res)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["match"])
    errors = sum(1 for r in results if r["error"])
    failed = total - passed - errors

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {passed} passed, {failed} failed, {errors} errors / {total} total")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 and errors == 0 else 1)


if __name__ == "__main__":
    main()
