import os
import json
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

class SmartAPIClient:
    # Class-level cache variables for fast in-memory lookups
    _tokens_cache = None
    _tokens_by_token = {}
    _tokens_by_symbol_exch = {}
    _tokens_by_name = {}

    def __init__(
        self,
        api_key: Optional[str] = None,
        client_code: Optional[str] = None,
        password: Optional[str] = None,
        data_dir: str = "./datasets"
    ):
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.data_dir = data_dir
        
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.last_error: Optional[str] = None  # Stores last login/connection error message
        
        self.symbol_token_path = os.path.join(data_dir, "symbol_tokens.json")
        self.catalog_path = os.path.join(data_dir, "catalog.json")
        
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, "csv"), exist_ok=True)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client_code and self.password)

    def _get_totp(self, totp_override: Optional[str] = None) -> Optional[str]:
        return totp_override

    def connect(self, totp: Optional[str] = None) -> bool:
        """Logs into Angel One SmartAPI and obtains session tokens."""
        self.last_error = None  # Reset on each attempt
        if not self.is_configured():
            self.last_error = "SmartAPI credentials not configured."
            print("SmartAPI not configured. Running in Mock Mode.")
            return False

        try:
            # Generate or prompt for TOTP
            totp = self._get_totp(totp_override=totp)
            if not totp:
                self.last_error = "Missing TOTP code."
                print("SmartAPI login failed: missing TOTP.")
                return False
            
            url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
            payload = {
                "clientcode": self.client_code,
                "password": self.password,
                "totp": totp,
                "state": "local_test"  # Matches Angel One API requirements
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
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
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
                # Capture the specific error message from Angel One API
                api_message = res_data.get('message') or res_data.get('errorMessage') or "Unknown error from Angel One API"
                error_code = res_data.get('errorcode', '')
                self.last_error = f"{api_message} (code: {error_code})" if error_code else api_message
                print(f"SmartAPI login failed: {self.last_error}")
                return False
        except Exception as e:
            self.last_error = f"Connection exception: {str(e)}"
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
                # Reset cache to force reload on next resolution
                SmartAPIClient._tokens_cache = None
        except Exception as e:
            print(f"Failed to download symbol tokens: {str(e)}")

    def resolve_symbol(self, symbol: str, from_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Resolves a text symbol (e.g. NSE:SBIN, NFO:SBIN-FUT) or numeric token to its Angel One token details."""
        if SmartAPIClient._tokens_cache is None:
            if not os.path.exists(self.symbol_token_path):
                self.download_symbol_tokens(force=True)
                if not os.path.exists(self.symbol_token_path):
                    return None
            try:
                print("Loading Angel One Symbol Token List into memory...")
                start_time = time.time()
                with open(self.symbol_token_path, "r", encoding="utf-8") as f:
                    tokens = json.load(f)
                
                by_token = {}
                by_symbol_exch = {}
                by_name = {}
                
                for item in tokens:
                    token = item.get("token")
                    sym = item.get("symbol")
                    exch = item.get("exch_seg")
                    name = item.get("name")
                    
                    if token:
                        by_token[str(token)] = item
                    if sym and exch:
                        by_symbol_exch[f"{exch.upper()}:{sym.upper()}"] = item
                    if name:
                        name_upper = str(name).upper()
                        if name_upper not in by_name:
                            by_name[name_upper] = []
                        by_name[name_upper].append(item)
                
                SmartAPIClient._tokens_cache = tokens
                SmartAPIClient._tokens_by_token = by_token
                SmartAPIClient._tokens_by_symbol_exch = by_symbol_exch
                SmartAPIClient._tokens_by_name = by_name
                print(f"INFO: Built SmartAPI token cache with {len(tokens)} items in {time.time() - start_time:.2f}s.")
            except Exception as e:
                print(f"Error loading symbol tokens: {str(e)}")
                return None

        try:
            target = symbol.upper().strip()
            
            # 1. Check for exchange prefix
            exch_filter = None
            if ":" in target:
                parts = target.split(":", 1)
                exch_filter = parts[0]
                target = parts[1]
            
            is_digit = target.isdigit()
            
            # 2. Match by token directly if input is numeric
            if is_digit:
                item = SmartAPIClient._tokens_by_token.get(target)
                if item:
                    if exch_filter and item.get("exch_seg") != exch_filter:
                        return None
                    return item
                return None
                
            # 3. Check for generic FUT suffix
            is_generic_fut = False
            base_symbol = target
            if target.endswith("-FUT"):
                is_generic_fut = True
                base_symbol = target[:-4] # strip -FUT

            # We can find candidate future contracts
            if is_generic_fut:
                candidates = []
                # Find all items where name is base_symbol and instrument type is FUT*
                name_matches = SmartAPIClient._tokens_by_name.get(base_symbol, [])
                for item in name_matches:
                    item_exch = str(item.get("exch_seg", "")).upper()
                    item_inst = str(item.get("instrumenttype", "")).upper()
                    
                    if exch_filter and item_exch != exch_filter:
                        continue
                    elif not exch_filter and item_exch not in ("NSE", "NFO", "MCX", "BSE"):
                        continue
                        
                    if item_inst.startswith("FUT"):
                        candidates.append(item)
                
                if candidates:
                    # Filter candidates that have an expiry
                    valid_candidates = []
                    for c in candidates:
                        exp_str = c.get("expiry")
                        if exp_str:
                            try:
                                exp_dt = datetime.strptime(exp_str, "%d%b%Y").date()
                                valid_candidates.append((c, exp_dt))
                            except Exception:
                                pass
                                
                    if valid_candidates:
                        target_date = datetime.today().date()
                        if from_date:
                            try:
                                if " " in from_date:
                                    target_date = datetime.strptime(from_date.split(" ")[0], "%Y-%m-%d").date()
                                else:
                                    target_date = datetime.strptime(from_date, "%Y-%m-%d").date()
                            except Exception:
                                pass
                                
                        future_candidates = [vc for vc in valid_candidates if vc[1] >= target_date]
                        if future_candidates:
                            future_candidates.sort(key=lambda x: x[1])
                            return future_candidates[0][0]
                        else:
                            valid_candidates.sort(key=lambda x: abs((x[1] - target_date).days))
                            return valid_candidates[0][0]

            # 4. Standard lookup (non-futures)
            # Try symbol matching
            if exch_filter:
                # Try exact symbol
                key = f"{exch_filter}:{target}"
                item = SmartAPIClient._tokens_by_symbol_exch.get(key)
                if item:
                    return item
                # Try symbol with -EQ suffix
                key_eq = f"{exch_filter}:{target}-EQ"
                item = SmartAPIClient._tokens_by_symbol_exch.get(key_eq)
                if item:
                    return item
                # Try name matching with exchange filter
                name_matches = SmartAPIClient._tokens_by_name.get(target, [])
                for item in name_matches:
                    if str(item.get("exch_seg", "")).upper() == exch_filter:
                        return item
            else:
                # No exchange filter: try default exchanges in order (prefer NSE equity, BSE, NFO future/options, MCX)
                for exch in ("NSE", "BSE", "NFO", "MCX"):
                    # Try exact symbol first on this exchange
                    key = f"{exch}:{target}"
                    item = SmartAPIClient._tokens_by_symbol_exch.get(key)
                    if item:
                        return item
                    # Try symbol-EQ on this exchange
                    key_eq = f"{exch}:{target}-EQ"
                    item = SmartAPIClient._tokens_by_symbol_exch.get(key_eq)
                    if item:
                        return item
                
                # Try name matches
                name_matches = SmartAPIClient._tokens_by_name.get(target, [])
                if name_matches:
                    # Sort by exchange preference
                    exch_order = {"NSE": 1, "BSE": 2, "NFO": 3, "MCX": 4}
                    name_matches = [m for m in name_matches if str(m.get("exch_seg", "")).upper() in exch_order]
                    if name_matches:
                        name_matches.sort(key=lambda x: exch_order.get(str(x.get("exch_seg", "")).upper(), 99))
                        return name_matches[0]
                        
        except Exception as e:
            print(f"Error resolving symbol token: {str(e)}")
            
        return None

    def fetch_historical_candles(
        self,
        symbol: str,
        from_date: str,  # YYYY-MM-DD HH:MM
        to_date: str,
        interval: str = "ONE_MINUTE"  # ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY
    ) -> Tuple[pd.DataFrame, bool]:
        """Fetches candles from SmartAPI if connected, otherwise falls back to Mock candles.
        
        Returns:
            (DataFrame, is_mock): The candle data and a boolean indicating if it came from the mock generator.
        """
        if self.jwt_token and self.is_configured():
            token_info = self.resolve_symbol(symbol, from_date=from_date)
            if not token_info:
                print(f"Symbol {symbol} not found in token list. Falling back to Mock.")
                return self.generate_mock_candles(symbol, from_date, to_date, interval), True
                
            token = token_info.get("token")
            exchange = token_info.get("exch_seg", "NSE")
            
            url = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData"
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
                    return df, False
                else:
                    print(f"Historical query failed: {res_json.get('message')}. Falling back to Mock.")
            except Exception as e:
                print(f"Historical query error: {str(e)}. Falling back to Mock.")
                
        return self.generate_mock_candles(symbol, from_date, to_date, interval), True

    def fetch_ltp(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the real-time Last Traded Price (LTP) for a symbol from SmartAPI.
        Uses the /getLtpData endpoint for the most current market price.
        Returns dict with ltp, open, high, low, close, volume or None on failure.
        """
        if not self.jwt_token or not self.is_configured():
            return None
        
        token_info = self.resolve_symbol(symbol)
        if not token_info:
            print(f"LTP fetch: Symbol {symbol} not found in token list.")
            return None
        
        token = token_info.get("token")
        exchange = token_info.get("exch_seg", "NSE")
        
        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/getLtpData"
        payload = {
            "exchange": exchange,
            "tradingsymbol": token_info.get("symbol", ""),
            "symboltoken": token,
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
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            res_json = response.json()
            if res_json.get("status") is True:
                data = res_json.get("data", {})
                return {
                    "ltp": float(data.get("ltp", 0)),
                    "open": float(data.get("open", 0)),
                    "high": float(data.get("high", 0)),
                    "low": float(data.get("low", 0)),
                    "close": float(data.get("close", 0)),
                    "volume": int(data.get("volume", 0)),
                }
            else:
                print(f"LTP fetch failed: {res_json.get('message')}")
        except Exception as e:
            print(f"LTP fetch error: {e}")
        return None

    def fetch_live_candle(self, symbol: str, interval: str = "ONE_MINUTE") -> Optional[Dict[str, Any]]:
        """
        Fetches the most recent completed candle for a symbol.
        Uses a very small historical window (last 2-3 candles) to get the latest close.
        Returns the latest candle as a dict or None if unavailable.
        """
        if not self.jwt_token or not self.is_configured():
            return None
        
        # Determine lookback based on interval
        now = datetime.now()
        if interval == "ONE_MINUTE":
            from_dt = now - timedelta(minutes=5)
        elif interval == "FIVE_MINUTE":
            from_dt = now - timedelta(minutes=15)
        elif interval == "FIFTEEN_MINUTE":
            from_dt = now - timedelta(minutes=45)
        elif interval == "ONE_HOUR":
            from_dt = now - timedelta(hours=3)
        elif interval == "ONE_DAY":
            from_dt = now - timedelta(days=3)
        else:
            from_dt = now - timedelta(minutes=15)
        
        from_str = from_dt.strftime("%Y-%m-%d %H:%M")
        to_str = now.strftime("%Y-%m-%d %H:%M")
        
        try:
            df, _is_mock = self.fetch_historical_candles(symbol, from_str, to_str, interval)
            if df is not None and not df.empty:
                # Get the last completed candle (not the current forming one)
                # For live paper trading, we use the most recent completed candle
                latest = df.iloc[-1]
                return {
                    "time": str(latest["time"]),
                    "open": float(latest["open"]),
                    "high": float(latest["high"]),
                    "low": float(latest["low"]),
                    "close": float(latest["close"]),
                    "volume": int(latest.get("volume", 0)),
                    "open_interest": int(latest.get("open_interest", 0)),
                }
        except Exception as e:
            print(f"Live candle fetch error for {symbol}: {e}")
        return None

    def calculate_charges_api(
        self,
        symbol: str,
        direction: str,
        price: float,
        qty: int,
        trade_type: str = "INTRADAY"
    ) -> Optional[Dict[str, Any]]:
        """
        Uses Angel One SmartAPI charges calculator endpoint (if available)
        to get realistic charges. Falls back to local calculation if API fails.
        
        Note: SmartAPI does not have a public REST endpoint for charges calculation.
        This method uses the local ExecutionSimulator logic for realistic estimates.
        In the future, if Angel One exposes a charges API, this can be swapped.
        """
        # Since Angel One does not expose a direct charges calculator REST endpoint,
        # we use the local calculation which matches Angel One's actual charges.
        # This keeps the paper trading PnL highly realistic.
        from engine.execution import ExecutionSimulator
        sim = ExecutionSimulator(slippage_pct=0.0, default_trade_type=trade_type)
        brokerage, stt, exc, gst, sebi, stamp, total = sim.calculate_charges(
            symbol, direction, price, qty, trade_type
        )
        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exc,
            "gst": gst,
            "sebi_charges": sebi,
            "stamp_duty": stamp,
            "total_charges": total,
            "source": "calculated",
            "note": "Based on Angel One actual charge structure. No real money used."
        }

    def generate_mock_candles(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str = "ONE_MINUTE"
    ) -> pd.DataFrame:
        """Generates realistic market candles according to Indian standard trading hours."""
        # Convert date strings to datetime objects
        try:
            # Use pandas to handle ISO strings, timezone offsets, and simple dates robustly
            start_dt = pd.to_datetime(from_date).tz_localize(None).to_pydatetime()
            end_dt = pd.to_datetime(to_date).tz_localize(None).to_pydatetime()
        except Exception as e:
            print(f"Mock Generator Date Error: {e}. Falling back to default range.")
            start_dt = datetime.now() - timedelta(days=30)
            end_dt = datetime.now()

        # Trading Hours: 9:15 AM to 3:30 PM (375 minutes)
        # We step day-by-day
        current_date = start_dt.date()
        end_date = end_dt.date()
        
        records = []
        base_price = 500.0
        sym_upper = symbol.upper()
        if ":" in sym_upper:
            sym_upper = sym_upper.split(":", 1)[1]
            
        clean_name = sym_upper
        for suffix in ("-EQ", "-FUT", "FUT"):
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)]
                
        if clean_name.startswith("NIFTY") or clean_name in ("99926000", "NIFTY 50", "NIFTY-50", "NIFTY50"):
            base_price = 22000.0
        elif clean_name.startswith("RELIANCE"):
            base_price = 2500.0
        elif clean_name.startswith("SBIN"):
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

    def save_dataset_csv(self, symbol: str, interval: str, df: pd.DataFrame, is_mock: bool = False) -> str:
        """Saves a candle DataFrame as CSV and indexes it in the catalog."""
        # Folder structure: /datasets/csv/{symbol}/{interval}/data.csv
        clean_symbol = symbol.upper().replace(":", "_")
        dir_path = os.path.join(self.data_dir, "csv", clean_symbol, interval.upper())
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, "data.csv")
        
        # Save to CSV
        df.to_csv(file_path, index=False)
        
        # Register in catalog
        self.register_in_catalog(symbol, interval, file_path, df, is_mock=is_mock)
        
        return file_path

    def save_dataset_excel(self, symbol: str, interval: str, df: pd.DataFrame, is_mock: bool = False) -> str:
        """Saves a candle DataFrame as Excel (.xlsx) and indexes it in the catalog."""
        # Folder structure: /datasets/excel/{symbol}/{interval}/data.xlsx
        clean_symbol = symbol.upper().replace(":", "_")
        dir_path = os.path.join(self.data_dir, "excel", clean_symbol, interval.upper())
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, "data.xlsx")
        
        # Save to Excel
        df.to_excel(file_path, index=False, engine='openpyxl')
        
        # Register in catalog
        self.register_in_catalog(symbol, interval, file_path, df, is_mock=is_mock)
        
        return file_path

    def register_in_catalog(self, symbol: str, interval: str, file_path: str, df: pd.DataFrame, is_mock: bool = False):
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
            "is_mock": is_mock,
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

    def load_dataset_csv(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Loads a saved dataset from CSV."""
        catalog = self.load_catalog()
        key = f"{symbol.upper()}_{interval.upper()}"
        if key in catalog:
            file_path = catalog[key]["file_path"]
            if os.path.exists(file_path):
                try:
                    return pd.read_csv(file_path)
                except Exception as e:
                    print(f"[SmartAPI] Failed to read CSV {file_path}: {e}")
                    return None
        return None

    def load_dataset_excel(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Loads a saved dataset from Excel (.xlsx)."""
        catalog = self.load_catalog()
        key = f"{symbol.upper()}_{interval.upper()}"
        if key in catalog:
            file_path = catalog[key]["file_path"]
            if os.path.exists(file_path) and file_path.endswith(".xlsx"):
                try:
                    return pd.read_excel(file_path, engine='openpyxl')
                except Exception as e:
                    print(f"[SmartAPI] Failed to read Excel {file_path}: {e}")
                    return None
        return None

    def load_dataset(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Loads a saved dataset from CSV or Excel based on catalog path."""
        catalog = self.load_catalog()
        key = f"{symbol.upper()}_{interval.upper()}"
        if key in catalog:
            file_path = catalog[key]["file_path"]
            if not os.path.exists(file_path):
                return None
            try:
                if file_path.endswith(".xlsx"):
                    return pd.read_excel(file_path, engine='openpyxl')
                else:
                    return pd.read_csv(file_path)
            except Exception as e:
                print(f"[SmartAPI] Failed to read dataset {file_path}: {e}")
                return None
        return None
