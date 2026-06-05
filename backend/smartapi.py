import os
import json
import time
import requests
import pyotp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class SmartAPIClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        client_code: Optional[str] = None,
        password: Optional[str] = None,
        totp_secret: Optional[str] = None,
        data_dir: str = "./datasets"
    ):
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        self.data_dir = data_dir
        
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        
        self.symbol_token_path = os.path.join(data_dir, "symbol_tokens.json")
        self.catalog_path = os.path.join(data_dir, "catalog.json")
        
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, "parquet"), exist_ok=True)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client_code and self.password)

    def _get_totp(self, totp_override: Optional[str] = None) -> Optional[str]:
        if totp_override:
            return totp_override
        if self.totp_secret:
            return pyotp.TOTP(self.totp_secret).now()
        env_totp = os.getenv("SMARTAPI_TOTP")
        if env_totp:
            return env_totp
        try:
            return input("Enter current TOTP: ").strip()
        except EOFError:
            return None

    def connect(self, totp: Optional[str] = None) -> bool:
        """Logs into Angel One SmartAPI and obtains session tokens."""
        if not self.is_configured():
            print("SmartAPI not configured. Running in Mock Mode.")
            return False

        try:
            # Generate or prompt for TOTP
            totp = self._get_totp(totp_override=totp)
            if not totp:
                print("SmartAPI login failed: missing TOTP.")
                return False
            
            url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
            payload = {
                "clientcode": self.client_code,
                "password": self.password,
                "totp": totp
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-PrivateKey": self.api_key,
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": os.getenv("SMARTAPI_CLIENT_LOCAL_IP", "127.0.0.1"),
                "X-ClientPublicIP": os.getenv("SMARTAPI_CLIENT_PUBLIC_IP", "127.0.0.1"),
                "X-MACAddress": os.getenv("SMARTAPI_MAC_ADDRESS", "00:00:00:00:00:00"),
            }
            
            response = requests.post(url, json=payload, headers=headers)
            res_data = response.json()
            
            if res_data.get("status") is True:
                token_data = res_data.get("data", {})
                self.jwt_token = token_data.get("jwtToken")
                self.refresh_token = token_data.get("refreshToken")
                self.feed_token = token_data.get("feedToken")
                print("Successfully authenticated with SmartAPI.")
                self.download_symbol_tokens()
                return True
            else:
                print(f"SmartAPI login failed: {res_data.get('message')}")
                return False
        except Exception as e:
            print(f"Exception during SmartAPI connection: {str(e)}")
            return False

    def download_symbol_tokens(self, force: bool = False):
        """Downloads the full Angel One symbol token mapping list."""
        if os.path.exists(self.symbol_token_path) and not force:
            # Check file age (cache for 24 hours)
            mtime = os.path.getmtime(self.symbol_token_path)
            if time.time() - mtime < 86400:
                return

        print("Downloading Angel One Symbol Token List...")
        try:
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            res = requests.get(url, timeout=30)
            if res.status_code == 200:
                with open(self.symbol_token_path, "w", encoding="utf-8") as f:
                    f.write(res.text)
                print("Symbol token map cached locally.")
        except Exception as e:
            print(f"Failed to download symbol tokens: {str(e)}")

    def resolve_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Resolves a text symbol (e.g. SBIN, RELIANCE) to its Angel One token details."""
        if not os.path.exists(self.symbol_token_path):
            self.download_symbol_tokens(force=True)
            if not os.path.exists(self.symbol_token_path):
                return None
                
        try:
            with open(self.symbol_token_path, "r") as f:
                tokens = json.load(f)
                
            # Search by symbol EQ (e.g. SBIN-EQ) or exact symbol match
            target = symbol.upper()
            target_eq = f"{target}-EQ"
            
            for item in tokens:
                if item.get("symbol") in (target, target_eq) and item.get("exch_seg") in ("NSE", "NFO"):
                    return item
        except Exception as e:
            print(f"Error resolving symbol token: {str(e)}")
            
        return None

    def fetch_historical_candles(
        self,
        symbol: str,
        from_date: str,  # YYYY-MM-DD HH:MM
        to_date: str,
        interval: str = "ONE_MINUTE"  # ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY
    ) -> pd.DataFrame:
        """Fetches candles from SmartAPI if connected, otherwise falls back to Mock candles."""
        if self.jwt_token and self.is_configured():
            token_info = self.resolve_symbol(symbol)
            if not token_info:
                print(f"Symbol {symbol} not found in token list. Falling back to Mock.")
                return self.generate_mock_candles(symbol, from_date, to_date, interval)
                
            token = token_info.get("token")
            exchange = token_info.get("exch_seg", "NSE")
            
            url = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleInfo"
            payload = {
                "exchange": exchange,
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.jwt_token}",
                "clientcode": self.client_code,
                "X-PrivateKey": self.api_key,
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": os.getenv("SMARTAPI_CLIENT_LOCAL_IP", "127.0.0.1"),
                "X-ClientPublicIP": os.getenv("SMARTAPI_CLIENT_PUBLIC_IP", "127.0.0.1"),
                "X-MACAddress": os.getenv("SMARTAPI_MAC_ADDRESS", "00:00:00:00:00:00"),
            }
            
            try:
                response = requests.post(url, json=payload, headers=headers)
                res_json = response.json()
                if res_json.get("status") is True:
                    data = res_json.get("data", [])
                    # Columns can be 6 or 7 depending on the instrument
                    if len(data) > 0:
                        num_cols = len(data[0])
                        if num_cols == 6:
                            cols = ["time", "open", "high", "low", "close", "volume"]
                            df = pd.DataFrame(data, columns=cols)
                            df["open_interest"] = 0
                        elif num_cols == 7:
                            cols = ["time", "open", "high", "low", "close", "volume", "open_interest"]
                            df = pd.DataFrame(data, columns=cols)
                        else:
                            # Fallback if unknown shape
                            cols = ["time", "open", "high", "low", "close", "volume"][:num_cols]
                            df = pd.DataFrame(data, columns=cols)
                    else:
                        df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume", "open_interest"])
                    return df
                else:
                    print(f"Historical query failed: {res_json.get('message')}. Falling back to Mock.")
            except Exception as e:
                print(f"Historical query error: {str(e)}. Falling back to Mock.")
                
        return self.generate_mock_candles(symbol, from_date, to_date, interval)

    def generate_mock_candles(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str = "ONE_MINUTE"
    ) -> pd.DataFrame:
        """Generates realistic market candles according to Indian standard trading hours."""
        # Convert date strings to datetime objects
        # Allowed formats: YYYY-MM-DD or YYYY-MM-DD HH:MM
        try:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d %H:%M")
        except ValueError:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d")
            
        try:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d %H:%M")
        except ValueError:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d")

        # Trading Hours: 9:15 AM to 3:30 PM (375 minutes)
        # We step day-by-day
        current_date = start_dt.date()
        end_date = end_dt.date()
        
        records = []
        base_price = 500.0
        if symbol.upper() == "NIFTY":
            base_price = 22000.0
        elif symbol.upper() == "RELIANCE":
            base_price = 2500.0
        elif symbol.upper() == "SBIN":
            base_price = 800.0
            
        np.random.seed(hash(symbol) % 1234567)

        # Resampling interval mapping
        step_minutes = 1
        if interval == "FIVE_MINUTE":
            step_minutes = 5
        elif interval == "FIFTEEN_MINUTE":
            step_minutes = 15
        elif interval == "ONE_HOUR":
            step_minutes = 60
        elif interval == "ONE_DAY":
            step_minutes = 375  # full session

        while current_date <= end_date:
            # Skip Saturday and Sunday
            if current_date.weekday() in (5, 6):
                current_date += timedelta(days=1)
                continue
                
            # Simulate a Daily Gap
            gap = np.random.normal(0, 0.006)  # ~0.6% daily gap standard deviation
            base_price *= (1.0 + gap)
            
            # Intraday loop
            dt_open = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=9, minutes=15)
            dt_close = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=15, minutes=30)
            
            current_bar = dt_open
            
            if interval == "ONE_DAY":
                # Single day bar
                ret = np.random.normal(0.0005, 0.015)
                close = base_price * (1 + ret)
                high = max(base_price, close) * (1 + abs(np.random.normal(0, 0.005)))
                low = min(base_price, close) * (1 - abs(np.random.normal(0, 0.005)))
                vol = int(np.random.lognormal(14, 0.5))
                records.append({
                    "time": current_bar.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": float(round(base_price, 2)),
                    "high": float(round(high, 2)),
                    "low": float(round(low, 2)),
                    "close": float(round(close, 2)),
                    "volume": vol,
                    "open_interest": 0
                })
                base_price = close
            else:
                while current_bar <= dt_close:
                    # Geometric Brownian Motion step
                    # Higher volatility at open (first 30 mins) and close (last 30 mins)
                    mins_from_open = (current_bar - dt_open).total_seconds() / 60
                    mins_to_close = (dt_close - current_bar).total_seconds() / 60
                    
                    volatility_multiplier = 1.0
                    if mins_from_open < 30 or mins_to_close < 30:
                        volatility_multiplier = 2.0  # double volatility during open/close
                        
                    step_ret = np.random.normal(0.00002, 0.0008 * volatility_multiplier)
                    
                    o = base_price
                    c = base_price * (1.0 + step_ret)
                    h = max(o, c) * (1.0 + abs(np.random.normal(0, 0.0003 * volatility_multiplier)))
                    l = min(o, c) * (1.0 - abs(np.random.normal(0, 0.0003 * volatility_multiplier)))
                    v = int(np.random.lognormal(9, 0.7) * volatility_multiplier)
                    
                    records.append({
                        "time": current_bar.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": float(round(o, 2)),
                        "high": float(round(h, 2)),
                        "low": float(round(l, 2)),
                        "close": float(round(c, 2)),
                        "volume": v,
                        "open_interest": 0
                    })
                    base_price = c
                    current_bar += timedelta(minutes=step_minutes)
            
            current_date += timedelta(days=1)
            
        return pd.DataFrame(records)

    def save_dataset_parquet(self, symbol: str, interval: str, df: pd.DataFrame) -> str:
        """Saves a candle DataFrame as Parquet and indexes it in the catalog."""
        # Folder structure: /datasets/parquet/{symbol}/{interval}/data.parquet
        dir_path = os.path.join(self.data_dir, "parquet", symbol.upper(), interval.upper())
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, "data.parquet")
        
        # Save to parquet
        df.to_parquet(file_path, index=False, engine='pyarrow')
        
        # Register in catalog
        self.register_in_catalog(symbol, interval, file_path, df)
        
        return file_path

    def register_in_catalog(self, symbol: str, interval: str, file_path: str, df: pd.DataFrame):
        """Indexes dataset details into local JSON catalog catalog.json."""
        catalog = {}
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, "r") as f:
                    catalog = json.load(f)
            except Exception:
                catalog = {}
                
        symbol = symbol.upper()
        interval = interval.upper()
        
        # Calculate min/max dates
        if not df.empty:
            start_date = df['time'].min()
            end_date = df['time'].max()
            num_rows = len(df)
        else:
            start_date = "N/A"
            end_date = "N/A"
            num_rows = 0
            
        key = f"{symbol}_{interval}"
        catalog[key] = {
            "symbol": symbol,
            "interval": interval,
            "file_path": os.path.abspath(file_path),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "records_count": num_rows,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(self.catalog_path, "w") as f:
            json.dump(catalog, f, indent=2)

    def load_catalog(self) -> Dict[str, Any]:
        """Loads the catalog metadata for downloaded datasets."""
        if not os.path.exists(self.catalog_path):
            return {}
        try:
            with open(self.catalog_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def load_dataset_parquet(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Loads a saved dataset from parquet."""
        catalog = self.load_catalog()
        key = f"{symbol.upper()}_{interval.upper()}"
        if key in catalog:
            file_path = catalog[key]["file_path"]
            if os.path.exists(file_path):
                return pd.read_parquet(file_path)
        return None
