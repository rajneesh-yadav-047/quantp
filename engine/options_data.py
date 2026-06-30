# engine/options_data.py
"""
Historical options OHLC data manager.

Handles downloading 1-minute candles from SmartAPI and serving them at any
requested interval, plus bulk import of NSE F&O EOD bhavcopy archives.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Tuple

from engine.options_catalog import resolve_token, ScripMasterLoader
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager


# Interval minutes mapping for resampling
_INTERVAL_MINUTES = {
    "ONE_MINUTE": 1,
    "THREE_MINUTE": 3,
    "FIVE_MINUTE": 5,
    "FIFTEEN_MINUTE": 15,
    "ONE_HOUR": 60,
    "ONE_DAY": 375,  # 9:15 to 15:30 = 375 minutes (used for tagging)
}

# Resample rule mapping
_RESAMPLE_RULE = {
    "ONE_MINUTE": "1min",
    "THREE_MINUTE": "3min",
    "FIVE_MINUTE": "5min",
    "FIFTEEN_MINUTE": "15min",
    "ONE_HOUR": "1h",
    "ONE_DAY": "1D",
}


def bsm_price(S: float, K: float, T: float, option_type: str, iv: float = 0.15, r: float = 0.065) -> float:
    """
    Black-Scholes price for a European option.

    Uses math.erf for the standard normal CDF (no scipy dependency).
    """
    import math

    if T <= 0:
        if option_type.upper() == "CE":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)

    sigma = iv
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    def ndf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    if option_type.upper() == "CE":
        price = S * ndf(d1) - K * math.exp(-r * T) * ndf(d2)
    else:
        price = K * math.exp(-r * T) * ndf(-d2) - S * ndf(-d1)

    return max(0.01, price)


def generate_bsm_candle(
    timestamp: str,
    S: float,
    K: float,
    T: float,
    option_type: str,
    iv: float = 0.15,
    r: float = 0.065,
    lot_size: int = 75,
) -> pd.DataFrame:
    """
    Generate a single synthetic OHLC candle using BSM pricing.
    Returns a DataFrame with the same schema as real options data.
    """
    price = bsm_price(S, K, T, option_type, iv, r)
    # Add small synthetic noise for open/high/low
    noise = price * 0.005
    return pd.DataFrame([{
        "datetime": pd.to_datetime(timestamp),
        "open": round(price - noise, 2),
        "high": round(price + noise, 2),
        "low": round(price - noise, 2),
        "close": round(price, 2),
        "volume": 1,
        "lot_size": lot_size,
        "interval": "ONE_MINUTE",
    }])


class OptionsDataManager:
    """
    Downloads and stores NFO option historical data as Parquet files.
    """

    def __init__(self, data_dir: str = "./datasets"):
        self.data_dir = data_dir
        self.options_dir = os.path.join(data_dir, "options", "NFO")
        os.makedirs(self.options_dir, exist_ok=True)

    @staticmethod
    def _parquet_path(
        data_dir: str,
        symbol: str,
        expiry: str,
        strike: float,
        option_type: str,
    ) -> str:
        """Return the canonical Parquet path for a contract."""
        safe_symbol = symbol.upper().replace(":", "_")
        safe_expiry = str(expiry)
        safe_strike = f"{float(strike):.2f}".replace(".", "_")
        dir_path = os.path.join(data_dir, "options", "NFO", safe_symbol, safe_expiry)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"{safe_strike}_{option_type.upper()}.parquet")

    def has_real_data(self, symbol: str, expiry: str, strike: float, option_type: str) -> bool:
        """Check if a Parquet file with real historical data exists for this contract."""
        parquet_path = self._parquet_path(self.data_dir, symbol, expiry, strike, option_type)
        return os.path.exists(parquet_path) and os.path.getsize(parquet_path) > 0

    def fetch_and_store(
        self,
        token: str,
        tradingsymbol: str,
        expiry: str,
        strike: float,
        option_type: str,
        lotsize: int,
        from_dt: str,
        to_dt: str,
    ) -> Optional[str]:
        """
        Download 1-minute candles from SmartAPI for a single NFO option contract
        and store them as a Parquet file.

        Args:
            token: Angel One symbol token.
            tradingsymbol: Trading symbol (e.g., "NIFTY30JUN26CE24000").
            expiry: Expiry date (YYYY-MM-DD).
            strike: Strike price.
            option_type: CE or PE.
            lotsize: Contract lot size.
            from_dt: Start datetime string (YYYY-MM-DD HH:MM).
            to_dt: End datetime string (YYYY-MM-DD HH:MM).

        Returns:
            Absolute path to the saved Parquet file, or None on failure.
        """
        client = SmartAPIManager.get_client()
        if not client or not client.jwt_token:
            client = SmartAPIManager.create_fresh_client()
        if not client or not client.jwt_token:
            print("ERROR: No authenticated SmartAPI client available for options download.")
            return None

        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData"
        payload = {
            "exchange": "NFO",
            "symboltoken": str(token),
            "interval": "ONE_MINUTE",
            "fromdate": from_dt,
            "todate": to_dt,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {client.jwt_token}",
            "clientcode": client.client_code or "",
            "X-PrivateKey": client.api_key or "",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": os.getenv("SMARTAPI_CLIENT_LOCAL_IP", "127.0.0.1"),
            "X-ClientPublicIP": os.getenv("SMARTAPI_CLIENT_PUBLIC_IP", "127.0.0.1"),
            "X-MACAddress": os.getenv("SMARTAPI_MAC_ADDRESS", "00:00:00:00:00:00"),
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            res_json = resp.json()
        except Exception as e:
            print(f"ERROR: SmartAPI request failed for {tradingsymbol}: {e}")
            return None

        if res_json.get("status") is not True:
            print(f"ERROR: SmartAPI returned error for {tradingsymbol}: {res_json.get('message')}")
            return None

        data = res_json.get("data", [])
        if not data:
            print(f"WARN: No candle data returned for {tradingsymbol}.")
            return None

        num_cols = len(data[0])
        if num_cols == 6:
            cols = ["time", "open", "high", "low", "close", "volume"]
        elif num_cols == 7:
            cols = ["time", "open", "high", "low", "close", "volume", "open_interest"]
        else:
            cols = ["time", "open", "high", "low", "close", "volume"][:num_cols]

        df = pd.DataFrame(data, columns=cols)
        df["datetime"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["datetime"])
        df["lot_size"] = int(lotsize)
        df["interval"] = "ONE_MINUTE"

        # Ensure schema columns
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df[["datetime", "open", "high", "low", "close", "volume", "lot_size", "interval"]]

        parquet_path = self._parquet_path(self.data_dir, tradingsymbol, expiry, strike, option_type)

        # Append to existing data if present, then deduplicate
        if os.path.exists(parquet_path):
            try:
                existing = pd.read_parquet(parquet_path)
                df = pd.concat([existing, df], ignore_index=True)
                df = df.drop_duplicates(subset=["datetime"], keep="last")
                df = df.sort_values("datetime").reset_index(drop=True)
            except Exception as e:
                print(f"WARN: Could not merge with existing Parquet for {tradingsymbol}: {e}")

        df.to_parquet(parquet_path, index=False)
        print(f"INFO: Saved {len(df)} rows to {parquet_path}")

        # Rate-limit padding
        time.sleep(0.35)
        return os.path.abspath(parquet_path)

    def get_ohlc(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        option_type: str,
        from_dt: str,
        to_dt: str,
        interval: str = "ONE_MINUTE",
    ) -> Optional[pd.DataFrame]:
        """
        Read stored 1-minute Parquet data and resample to the requested interval.

        Args:
            symbol: Underlying symbol name.
            expiry: Expiry date (YYYY-MM-DD).
            strike: Strike price.
            option_type: CE or PE.
            from_dt: Start date string (YYYY-MM-DD).
            to_dt: End date string (YYYY-MM-DD).
            interval: Target interval (ONE_MINUTE, THREE_MINUTE, FIVE_MINUTE,
                      FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY).

        Returns:
            DataFrame with columns [datetime, open, high, low, close, volume, lot_size, interval]
            or None if no data is stored.
        """
        parquet_path = self._parquet_path(self.data_dir, symbol, expiry, strike, option_type)
        if not os.path.exists(parquet_path):
            return None

        df = pd.read_parquet(parquet_path)
        if df.empty:
            return None

        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])
        df = df.sort_values("datetime")

        # Filter date range
        start = pd.to_datetime(from_dt)
        end = pd.to_datetime(to_dt) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df = df[(df["datetime"] >= start) & (df["datetime"] <= end)]

        if df.empty:
            return None

        interval = interval.upper()
        if interval == "ONE_MINUTE":
            df["interval"] = "ONE_MINUTE"
            return df.reset_index(drop=True)

        rule = _RESAMPLE_RULE.get(interval, interval.lower())

        # Resample with OHLC aggregation and volume sum
        df = df.set_index("datetime")
        resampled = df.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "lot_size": "last",
        }).dropna()
        resampled["interval"] = interval
        resampled = resampled.reset_index()
        return resampled


# ── NSE Bhavcopy bulk import ──

def _nse_bhavcopy_url(trading_date: date) -> str:
    """Build NSE F&O bhavcopy URL for a given trading date."""
    yyyymmdd = trading_date.strftime("%Y%m%d")
    return (
        f"https://archives.nseindia.com/content/fo/"
        f"BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    )


def _parse_bhavcopy_date(val) -> Optional[datetime]:
    """Parse NSE bhavcopy date formats (YYYY-MM-DD or DD-MMM-YYYY)."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _trading_dates_between(start: date, end: date) -> List[date]:
    dates = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # Mon-Fri
            dates.append(cur)
        cur += timedelta(days=1)
    return dates


def bulk_import_nse_bhavcopy(
    from_date: str,
    to_date: str,
    data_dir: str = "./datasets",
    sync_progress=None,
) -> Dict[str, Any]:
    """
    Loop through each trading day in the range, download the NSE F&O UDiFF
    bhavcopy ZIP, unzip and parse it, and write EOD option rows into the
    same Parquet structure used by the live collector.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        data_dir: Root datasets directory.

    Returns:
        Summary dict with days_processed, contracts_imported, errors, etc.
    """
    start = datetime.strptime(from_date, "%Y-%m-%d").date()
    end = datetime.strptime(to_date, "%Y-%m-%d").date()
    dates = _trading_dates_between(start, end)

    manager = OptionsDataManager(data_dir=data_dir)
    loader = ScripMasterLoader(data_dir=data_dir)

    summary = {
        "days_processed": 0,
        "contracts_imported": 0,
        "errors": [],
        "files_created": set(),
    }

    for td in dates:
        url = _nse_bhavcopy_url(td)
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                summary["errors"].append(f"{td.isoformat()}: HTTP {resp.status_code}")
                continue
        except Exception as e:
            summary["errors"].append(f"{td.isoformat()}: download error {e}")
            continue

        # Save zip to temp
        import zipfile
        import io

        try:
            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
            with z.open(csv_name) as f:
                # NSE bhavcopy is pipe-delimited
                df = pd.read_csv(f, delimiter="|", low_memory=False)
        except Exception as e:
            summary["errors"].append(f"{td.isoformat()}: parse error {e}")
            continue

        # Filter option rows
        if "OptnTp" not in df.columns:
            summary["errors"].append(f"{td.isoformat()}: missing OptnTp column")
            continue

        df_opts = df[df["OptnTp"].isin(["CE", "PE"])].copy()
        if df_opts.empty:
            summary["days_processed"] += 1
            continue

        # Normalize columns
        col_map = {
            "TradDt": "date",
            "TckrSymb": "symbol",
            "XpryDt": "expiry",
            "StrkPric": "strike",
            "OptnTp": "option_type",
            "OpnPric": "open",
            "HghPric": "high",
            "LwPric": "low",
            "ClsPric": "close",
            "TtlTradgVol": "volume",
        }
        for old, new in col_map.items():
            if old in df_opts.columns:
                df_opts[new] = df_opts[old]

        df_opts["date"] = df_opts["date"].apply(lambda x: _parse_bhavcopy_date(x))
        df_opts = df_opts.dropna(subset=["date", "symbol", "expiry", "strike", "option_type"])
        df_opts["strike"] = pd.to_numeric(df_opts["strike"], errors="coerce")
        df_opts = df_opts.dropna(subset=["strike"])

        for _, row in df_opts.iterrows():
            try:
                symbol = str(row["symbol"]).strip().upper()
                expiry_dt = _parse_bhavcopy_date(row["expiry"])
                if expiry_dt is None:
                    continue
                expiry_iso = expiry_dt.date().isoformat()
                strike = float(row["strike"])
                option_type = str(row["option_type"]).upper()

                # Resolve lot size from catalog (best-effort)
                catalog_info = resolve_token(
                    symbol, expiry_iso, strike, option_type,
                    fallback_to_snapshots=True, data_dir=data_dir
                )
                lotsize = int(catalog_info["lotsize"]) if catalog_info and catalog_info.get("lotsize") else 1

                # Build single EOD row
                eod_row = pd.DataFrame([{
                    "datetime": pd.Timestamp(row["date"]).normalize(),
                    "open": float(row["open"]) if pd.notna(row.get("open")) else 0.0,
                    "high": float(row["high"]) if pd.notna(row.get("high")) else 0.0,
                    "low": float(row["low"]) if pd.notna(row.get("low")) else 0.0,
                    "close": float(row["close"]) if pd.notna(row.get("close")) else 0.0,
                    "volume": int(row["volume"]) if pd.notna(row.get("volume")) else 0,
                    "lot_size": lotsize,
                    "interval": "ONE_DAY",
                }])

                parquet_path = manager._parquet_path(data_dir, symbol, expiry_iso, strike, option_type)

                if os.path.exists(parquet_path):
                    existing = pd.read_parquet(parquet_path)
                    eod_row = pd.concat([existing, eod_row], ignore_index=True)
                    eod_row = eod_row.drop_duplicates(subset=["datetime"], keep="last")
                    eod_row = eod_row.sort_values("datetime").reset_index(drop=True)

                eod_row.to_parquet(parquet_path, index=False)
                summary["files_created"].add(parquet_path)
                summary["contracts_imported"] += 1
            except Exception as e:
                summary["errors"].append(f"{td.isoformat()} row error: {e}")
                continue

        summary["days_processed"] += 1
        if sync_progress and dates:
            sync_progress(int((summary["days_processed"] / len(dates)) * 100))

    summary["files_created"] = list(summary["files_created"])
    return summary
