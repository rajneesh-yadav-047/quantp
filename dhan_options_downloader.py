"""
dhan_options_downloader.py  —  CORRECTED for Dhan API v2 /charts/rollingoption

Downloads expired NIFTY option historical data from DhanHQ and saves to Parquet
matching the exact schema expected by engine/options_data.py.

Based on official Dhan docs: https://dhanhq.co/docs/v2/expired-options-data/

Payload schema (POST /v2/charts/rollingoption):
    exchangeSegment : "NSE_FNO"
    interval      : "1" | "5" | "15" | "25" | "60"  (required)
    securityId    : int  (13 for NIFTY index)
    instrument    : "OPTIDX"
    expiryFlag    : "WEEK" | "MONTH"
    expiryCode    : 1 | 2 | 3  (1=first expiry in range, NOT 0)
    strike        : "ATM" | "ATM-1" ... "ATM-10" | "ATM+1" ... "ATM+10"
    drvOptionType : "CALL" | "PUT"
    requiredData  : ["open","high","low","close","volume","iv","oi","strike","spot"]
    fromDate      : "YYYY-MM-DD"
    toDate        : "YYYY-MM-DD"  (non-inclusive)

Response shape (columnar):
    {"data": {"ce": {...}, "pe": {...}}}
    Each section has: open[], high[], low[], close[], volume[], timestamp[],
                      iv[], oi[], strike[], spot[]

Usage:
    py dhan_options_downloader.py --start 2026-01-01 --end 2026-05-31
"""

import os
import sys
import time
import json
import argparse
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Tuple
import io

# ── Configuration ──────────────────────────────────────────────────────────
DHAN_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
DHAN_API_BASE = "https://api.dhan.co"
DHAN_SANDBOX_BASE = "https://sandbox.dhan.co"
OUTPUT_DIR = Path("./datasets/options/NFO")
CACHE_DIR = Path("./datasets/.cache/dhan")
RATE_LIMIT_DELAY = 0.5  # seconds between API calls
MAX_STRIKE_OFFSET = 10   # ATM±10 for index options per Dhan docs
NIFTY_SECURITY_ID = 13
NIFTY_STRIKE_STEP = 50

REQUIRED_COLS = ["datetime", "open", "high", "low", "close", "volume", "lot_size", "interval"]


def _get_env_credentials() -> Tuple[str, str]:
    cid = os.environ.get("DHAN_CLIENT_ID")
    tok = os.environ.get("DHAN_ACCESS_TOKEN")
    if not cid or not tok:
        print("ERROR: Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN environment variables.")
        sys.exit(1)
    return cid, tok


def _ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _detect_sandbox(token: str) -> bool:
    """Heuristic: if the JWT contains sandbox.dhan.co, it's a sandbox token."""
    try:
        payload_b64 = token.split(".")[1]
        import base64
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(padded).decode("utf-8"))
        webhook = payload.get("webhookUrl", "")
        return "sandbox" in webhook.lower()
    except Exception:
        return False


def _get_api_base(token: str, force_sandbox: bool = False) -> str:
    if force_sandbox or _detect_sandbox(token):
        return DHAN_SANDBOX_BASE
    return DHAN_API_BASE


def _dhan_headers(access_token: str) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": access_token,
    }


# ── Master CSV (optional — used to verify NIFTY securityId) ────────────────

def download_master_instruments(force: bool = False) -> Optional[pd.DataFrame]:
    cache_file = CACHE_DIR / "api-scrip-master.csv"
    meta_file = CACHE_DIR / "master-meta.json"
    today_iso = date.today().isoformat()

    if not force and cache_file.exists() and meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("date") == today_iso:
                return pd.read_csv(cache_file, low_memory=False)
        except Exception:
            pass

    print(f"INFO: Downloading Dhan master instrument list...")
    try:
        resp = requests.get(DHAN_MASTER_URL, timeout=60)
        resp.raise_for_status()
        cache_file.write_bytes(resp.content)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"date": today_iso, "url": DHAN_MASTER_URL}, f)
        print(f"INFO: Cached master list ({len(resp.content):,} bytes)")
        return pd.read_csv(io.BytesIO(resp.content), low_memory=False)
    except Exception as e:
        print(f"WARN: Failed to download master list: {e}")
        if cache_file.exists():
            return pd.read_csv(cache_file, low_memory=False)
        return None


# ── Rolling Options API ────────────────────────────────────────────────────

def build_strike_list(max_offset: int = 10) -> List[str]:
    """Generate strike identifiers: [ATM-10, ..., ATM-1, ATM, ATM+1, ..., ATM+10]."""
    strikes = ["ATM"]
    for i in range(1, max_offset + 1):
        strikes.append(f"ATM-{i}")
        strikes.append(f"ATM+{i}")
    return strikes


def fetch_rolling_option(
    access_token: str,
    from_date: str,
    to_date: str,
    api_base: str = DHAN_API_BASE,
    exchange_segment: str = "NSE_FNO",
    interval: str = "1",
    security_id: int = NIFTY_SECURITY_ID,
    instrument: str = "OPTIDX",
    expiry_flag: str = "WEEK",
    expiry_code: int = 1,
    strike: str = "ATM",
    drv_option_type: str = "CALL",
    required_data: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call Dhan POST /v2/charts/rollingoption for ONE specific contract.
    Returns raw JSON dict or None if no data / error.
    """
    if required_data is None:
        required_data = ["open", "high", "low", "close", "volume", "iv", "oi", "strike", "spot"]

    url = f"{api_base}/v2/charts/rollingoption"
    headers = _dhan_headers(access_token)
    payload = {
        "exchangeSegment": exchange_segment,
        "interval": interval,
        "securityId": security_id,
        "instrument": instrument,
        "expiryFlag": expiry_flag,
        "expiryCode": expiry_code,
        "strike": strike,
        "drvOptionType": drv_option_type,
        "requiredData": required_data,
        "fromDate": from_date,
        "toDate": to_date,
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"WARN: Rate limited (429). Sleeping {wait}s before retry {attempt}/{max_retries}...")
                time.sleep(wait)
                continue
            if resp.status_code == 400:
                # Parse error to see if it's a known issue
                try:
                    err = resp.json()
                    err_code = err.get("errorCode", "")
                    err_msg = err.get("errorMessage", "")
                    if err_code == "DH-905":
                        print(f"WARN: DH-905 ({err_msg}) for {expiry_code}/{strike}/{drv_option_type}")
                    else:
                        print(f"WARN: HTTP 400: {err}")
                except Exception:
                    print(f"WARN: HTTP 400: {resp.text[:200]}")
                return None
            if resp.status_code == 401:
                print(f"ERROR: HTTP 401 Unauthorized — token may be expired.")
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Request failed (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return None

    return None


def parse_columnar_response(data: Dict[str, Any], option_type: str, lot_size: int = 75) -> Optional[pd.DataFrame]:
    """
    Parse Dhan columnar response for one option type (ce or pe).
    Returns DataFrame with canonical columns, or None if empty.
    """
    if not data or not isinstance(data, dict):
        return None

    root = data.get("data", {})
    section = root.get(option_type.lower())  # "ce" or "pe"
    if section is None:
        return None

    timestamps = section.get("timestamp", [])
    if not timestamps:
        return None

    # Build row-based DataFrame from columnar arrays
    rows = []
    for i in range(len(timestamps)):
        def _get(arr, idx, default=None):
            return arr[idx] if idx < len(arr) else default

        rows.append({
            "timestamp": timestamps[i],
            "open": _get(section.get("open", []), i),
            "high": _get(section.get("high", []), i),
            "low": _get(section.get("low", []), i),
            "close": _get(section.get("close", []), i),
            "volume": _get(section.get("volume", []), i, 0),
            "iv": _get(section.get("iv", []), i),
            "oi": _get(section.get("oi", []), i),
            "strike": _get(section.get("strike", []), i),
            "spot": _get(section.get("spot", []), i),
        })

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        return None

    # Parse timestamp (epoch seconds)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
    df = df.dropna(subset=["datetime"])

    # Ensure numeric
    for col in ["open", "high", "low", "close", "volume", "iv", "oi", "strike", "spot"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["lot_size"] = lot_size
    df["interval"] = "ONE_MINUTE"

    return df[["datetime", "open", "high", "low", "close", "volume", "iv", "oi", "strike", "spot", "lot_size", "interval"]]


# ── Parquet I/O ───────────────────────────────────────────────────────────

def _safe_symbol(symbol: str) -> str:
    return symbol.upper().replace(":", "_")


def _safe_strike(strike: float) -> str:
    return f"{float(strike):.2f}".replace(".", "_")


def parquet_path(symbol: str, expiry: str, strike: float, option_type: str) -> Path:
    safe_symbol = _safe_symbol(symbol)
    safe_expiry = str(expiry)
    safe_strike = _safe_strike(strike)
    dir_path = OUTPUT_DIR / safe_symbol / safe_expiry
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / f"{safe_strike}_{option_type.upper()}.parquet"


def save_parquet(df: pd.DataFrame, path: Path, merge: bool = True) -> None:
    """Save DataFrame to Parquet, merging + deduplicating if file exists."""
    if df.empty:
        print(f"WARN: Empty DataFrame, skipping {path}")
        return

    for col in REQUIRED_COLS:
        if col not in df.columns:
            if col == "lot_size":
                df[col] = 75
            elif col == "interval":
                df[col] = "ONE_MINUTE"
            else:
                df[col] = None

    df = df[REQUIRED_COLS]

    if path.exists() and merge:
        try:
            existing = pd.read_parquet(path)
            df = pd.concat([existing, df], ignore_index=True)
            df = df.drop_duplicates(subset=["datetime"], keep="last")
            df = df.sort_values("datetime").reset_index(drop=True)
        except Exception as e:
            print(f"WARN: Could not merge with existing {path}: {e}")

    df.to_parquet(path, index=False)
    print(f"INFO: Saved {len(df)} rows -> {path}")


# ── Date helpers ───────────────────────────────────────────────────────────

def date_chunks(start: datetime, end: datetime, chunk_days: int = 30) -> List[Tuple[str, str]]:
    """Generate (from_date, to_date) string pairs."""
    chunks = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=chunk_days), end)
        chunks.append((cur.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        cur = nxt + timedelta(days=1)
    return chunks


def thursday_expiries(start: date, end: date) -> List[str]:
    """Return weekly Thursday expiry ISO strings."""
    dates = []
    cur = start
    while cur <= end:
        days_to_thu = (3 - cur.weekday()) % 7
        expiry = cur + timedelta(days=days_to_thu)
        if expiry <= end:
            dates.append(expiry.isoformat())
        cur += timedelta(days=7)
    return sorted(set(dates))


# ── Core download orchestrator ───────────────────────────────────────────

def download_expiry_contracts(
    access_token: str,
    symbol: str,
    from_date: str,
    to_date: str,
    api_base: str = DHAN_API_BASE,
    expiry_flag: str = "WEEK",
    expiry_code: int = 1,
    lot_size: int = 75,
    max_offset: int = 10,
) -> Dict[str, int]:
    """
    Download ALL strikes (ATM±max_offset) for ONE expiryCode in a date range.
    Returns summary dict with counts.
    """
    strikes = build_strike_list(max_offset)
    summary = {"calls_saved": 0, "puts_saved": 0, "empty_calls": 0, "empty_puts": 0, "errors": 0}

    for strike in strikes:
        # --- CALL ---
        time.sleep(RATE_LIMIT_DELAY)
        raw = fetch_rolling_option(
            access_token=access_token,
            from_date=from_date,
            to_date=to_date,
            api_base=api_base,
            expiry_flag=expiry_flag,
            expiry_code=expiry_code,
            strike=strike,
            drv_option_type="CALL",
        )
        if raw is None:
            summary["errors"] += 1
        else:
            df = parse_columnar_response(raw, "ce", lot_size=lot_size)
            if df is None or df.empty:
                summary["empty_calls"] += 1
            else:
                actual_strike = df["strike"].dropna().iloc[0] if "strike" in df.columns and not df["strike"].dropna().empty else None
                if actual_strike is None:
                    print(f"WARN: Could not resolve strike for {strike} CALL. Skipping save.")
                    summary["empty_calls"] += 1
                else:
                    actual_strike_f = float(actual_strike)
                    # Infer expiry from timestamps — the last day in the data is likely expiry
                    last_ts = df["datetime"].max()
                    inferred_expiry = last_ts.date().isoformat() if pd.notna(last_ts) else f"{from_date}_{expiry_code}"
                    path = parquet_path(symbol, inferred_expiry, actual_strike_f, "CE")
                    save_parquet(df, path, merge=True)
                    summary["calls_saved"] += 1

        # --- PUT ---
        time.sleep(RATE_LIMIT_DELAY)
        raw = fetch_rolling_option(
            access_token=access_token,
            from_date=from_date,
            to_date=to_date,
            api_base=api_base,
            expiry_flag=expiry_flag,
            expiry_code=expiry_code,
            strike=strike,
            drv_option_type="PUT",
        )
        if raw is None:
            summary["errors"] += 1
        else:
            df = parse_columnar_response(raw, "pe", lot_size=lot_size)
            if df is None or df.empty:
                summary["empty_puts"] += 1
            else:
                actual_strike = df["strike"].dropna().iloc[0] if "strike" in df.columns and not df["strike"].dropna().empty else None
                if actual_strike is None:
                    print(f"WARN: Could not resolve strike for {strike} PUT. Skipping save.")
                    summary["empty_puts"] += 1
                else:
                    actual_strike_f = float(actual_strike)
                    last_ts = df["datetime"].max()
                    inferred_expiry = last_ts.date().isoformat() if pd.notna(last_ts) else f"{from_date}_{expiry_code}"
                    path = parquet_path(symbol, inferred_expiry, actual_strike_f, "PE")
                    save_parquet(df, path, merge=True)
                    summary["puts_saved"] += 1

    return summary


def main():
    parser = argparse.ArgumentParser(description="Dhan NIFTY Expired Options Data Downloader")
    parser.add_argument("--start", type=str, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Underlying symbol (default: NIFTY)")
    parser.add_argument("--expiry-flag", type=str, default="WEEK", choices=["WEEK", "MONTH"], help="WEEK or MONTH")
    parser.add_argument("--lot-size", type=int, default=75, help="Contract lot size")
    parser.add_argument("--max-offset", type=int, default=10, help="Max ATM strike offset (default: 10)")
    parser.add_argument("--security-id", type=int, default=NIFTY_SECURITY_ID, help="Dhan securityId for underlying")
    parser.add_argument("--sandbox", action="store_true", help="Force sandbox endpoint (https://sandbox.dhan.co)")
    parser.add_argument("--force-master", action="store_true", help="Force re-download master CSV")
    args = parser.parse_args()

    client_id, access_token = _get_env_credentials()
    _ensure_dirs()

    api_base = _get_api_base(access_token, force_sandbox=args.sandbox)
    is_sandbox = _detect_sandbox(access_token) or args.sandbox

    print(f"INFO: Dhan client_id={client_id}")
    print(f"INFO: API endpoint: {api_base}")
    if is_sandbox:
        print(f"WARN: Using SANDBOX endpoint. Historical data may not be available. Generate a production token from Dhan dashboard for full data access.")
    print(f"INFO: Download period {args.start} -> {args.end} for {args.symbol}")
    print(f"INFO: expiryFlag={args.expiry_flag}, maxOffset={args.max_offset}, lotSize={args.lot_size}")

    # Optional: download master to verify NIFTY securityId
    master_df = download_master_instruments(force=args.force_master)
    if master_df is not None:
        nifty_idx = master_df[
            (master_df.get("SEM_TRADING_SYMBOL", "").str.strip().str.upper() == "NIFTY") &
            (master_df.get("SEM_EXCH_INSTRUMENT_TYPE", "").str.strip().str.upper() == "IDX")
        ]
        if not nifty_idx.empty:
            resolved = int(str(nifty_idx.iloc[0]["SEM_SMST_SECURITY_ID"]).strip())
            if resolved != args.security_id:
                print(f"INFO: Resolved NIFTY securityId from master = {resolved} (overriding {args.security_id})")
                args.security_id = resolved

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    chunks = date_chunks(start_dt, end_dt, chunk_days=30)

    total_calls = 0
    total_puts = 0
    total_errors = 0

    for from_d, to_d in chunks:
        print(f"\n=== Chunk: {from_d} -> {to_d} ===")
        # Try expiryCode 1, 2, 3, 4, 5 until we hit empty data
        for expiry_code in range(1, 6):
            print(f"\n-- expiryCode={expiry_code} --")
            summary = download_expiry_contracts(
                access_token=access_token,
                symbol=args.symbol,
                from_date=from_d,
                to_date=to_d,
                api_base=api_base,
                expiry_flag=args.expiry_flag,
                expiry_code=expiry_code,
                lot_size=args.lot_size,
                max_offset=args.max_offset,
            )
            total_calls += summary["calls_saved"]
            total_puts += summary["puts_saved"]
            total_errors += summary["errors"]

            # If both CE and PE returned empty for all strikes, this expiryCode doesn't exist in this chunk
            if summary["calls_saved"] == 0 and summary["puts_saved"] == 0 and summary["errors"] == 0:
                print(f"INFO: No data for expiryCode={expiry_code} in {from_d}->{to_d}. Stopping chunk.")
                break

    print(f"\n=== DONE ===")
    print(f"Total CE contracts saved: {total_calls}")
    print(f"Total PE contracts saved: {total_puts}")
    print(f"Total errors: {total_errors}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
