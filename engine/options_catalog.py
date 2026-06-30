# engine/options_catalog.py
"""
Single source of truth for all NFO (NSE Futures & Options) contract metadata.

Downloads the Angel One ScripMaster JSON, filters for NFO option contracts
(OPTIDX and OPTSTK), builds an in-memory lookup, and supports snapshotting
and token resolution for expired contracts.
"""

import os
import json
import time
import requests
from datetime import datetime, date
from typing import Dict, Optional, Any, List


SCRIP_MASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)


def _to_iso_date(d) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


class ScripMasterLoader:
    """
    Downloads the Angel One ScripMaster, filters for NFO option contracts,
    and builds an in-memory lookup indexed by (name, expiry_date, strike, option_type).
    """

    def __init__(self, data_dir: str = "./datasets"):
        self.data_dir = data_dir
        self._raw_rows: List[Dict[str, Any]] = []
        self._lookup: Dict[str, Dict[str, Any]] = {}
        self._last_loaded: Optional[float] = None

    def _build_key(self, name: str, expiry_date: str, strike: float, option_type: str) -> str:
        return f"{name.upper()}|{expiry_date}|{float(strike)}|{option_type.upper()}"

    def download(self, force: bool = False) -> List[Dict[str, Any]]:
        """Download and filter the ScripMaster for NFO options."""
        cache_path = os.path.join(self.data_dir, "symbol_tokens.json")

        if not force and os.path.exists(cache_path):
            mtime = os.path.getmtime(cache_path)
            if self._last_loaded and self._last_loaded >= mtime and self._raw_rows:
                return self._raw_rows
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    tokens = json.load(f)
            except Exception as e:
                print(f"WARN: Failed to load cached symbol tokens: {e}. Re-downloading.")
                tokens = None
        else:
            tokens = None

        if tokens is None:
            print("Downloading Angel One ScripMaster...")
            try:
                resp = requests.get(SCRIP_MASTER_URL, timeout=30)
                resp.raise_for_status()
                tokens = resp.json()
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(tokens, f, ensure_ascii=False)
                print(f"Cached ScripMaster ({len(tokens)} rows) to {cache_path}")
            except Exception as e:
                print(f"ERROR: Failed to download ScripMaster: {e}")
                if os.path.exists(cache_path):
                    try:
                        with open(cache_path, "r", encoding="utf-8") as f:
                            tokens = json.load(f)
                    except Exception:
                        tokens = []
                else:
                    tokens = []

        self._raw_rows = self._filter_nfo_options(tokens)
        self._build_lookup()
        self._last_loaded = time.time()
        return self._raw_rows

    def _filter_nfo_options(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter rows where exch_seg == NFO and instrumenttype is OPTIDX or OPTSTK."""
        filtered = []
        for item in tokens:
            exch = str(item.get("exch_seg", "")).upper()
            inst = str(item.get("instrumenttype", "")).upper()
            if exch == "NFO" and inst in ("OPTIDX", "OPTSTK"):
                filtered.append(dict(item))
        return filtered

    def _build_lookup(self) -> None:
        """Build the in-memory lookup dictionary."""
        self._lookup = {}
        for item in self._raw_rows:
            name = str(item.get("name", "")).upper()
            expiry = item.get("expiry")
            strike = item.get("strike")
            option_type = str(item.get("symbol", "")).upper().split("-")[-1] if item.get("symbol") else ""
            # Some rows use "symbol" as tradingsymbol and the last token is CE/PE
            if option_type not in ("CE", "PE"):
                # Fallback: try to infer from tradingsymbol or symbol field
                sym = str(item.get("symbol", "")).upper()
                if sym.endswith("-CE") or sym.endswith("CE"):
                    option_type = "CE"
                elif sym.endswith("-PE") or sym.endswith("PE"):
                    option_type = "PE"
                else:
                    continue

            # Normalize expiry to ISO date string
            if expiry:
                try:
                    # Angel One format is usually "DDMonYYYY" e.g. "26JUN2026"
                    expiry_dt = datetime.strptime(str(expiry), "%d%b%Y")
                    expiry_iso = expiry_dt.date().isoformat()
                except Exception:
                    expiry_iso = str(expiry)
            else:
                expiry_iso = ""

            try:
                strike_f = float(strike) if strike is not None else 0.0
            except Exception:
                strike_f = 0.0

            key = self._build_key(name, expiry_iso, strike_f, option_type)
            self._lookup[key] = {
                "token": item.get("token"),
                "lotsize": item.get("lotsize"),
                "tick_size": item.get("tick_size"),
                "tradingsymbol": item.get("symbol"),
                "name": name,
                "expiry_date": expiry_iso,
                "strike": strike_f,
                "option_type": option_type,
                "exch_seg": "NFO",
                "instrumenttype": item.get("instrumenttype"),
            }

    def get_contract(self, name: str, expiry_date: str, strike: float, option_type: str) -> Optional[Dict[str, Any]]:
        """Look up a contract in the live (current) ScripMaster."""
        if not self._raw_rows:
            self.download()
        key = self._build_key(name, expiry_date, strike, option_type)
        return self._lookup.get(key)

    def all_contracts(self) -> List[Dict[str, Any]]:
        """Return all current NFO option contracts."""
        if not self._raw_rows:
            self.download()
        return list(self._raw_rows)

    def contracts_expiring_on(self, expiry_date: str) -> List[Dict[str, Any]]:
        """Return all contracts with the given expiry date."""
        if not self._raw_rows:
            self.download()
        iso = _to_iso_date(expiry_date)
        return [row for row in self._raw_rows if self._extract_expiry(row) == iso]

    @staticmethod
    def _extract_expiry(row: Dict[str, Any]) -> str:
        expiry = row.get("expiry")
        if not expiry:
            return ""
        try:
            return datetime.strptime(str(expiry), "%d%b%Y").date().isoformat()
        except Exception:
            return str(expiry)


# ── Snapshot helpers ──

def save_daily_snapshot(date_str: Optional[str] = None, data_dir: str = "./datasets") -> str:
    """
    Save the raw filtered NFO rows as a JSON snapshot so expired contracts
    can be resolved later.  Must be called *before* 3:30 PM on expiry day
    because SmartAPI removes expired contracts from the live master immediately.

    Args:
        date_str: ISO date string (YYYY-MM-DD). Defaults to today.
        data_dir: Root datasets directory.

    Returns:
        Absolute path to the saved snapshot file.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    snapshot_dir = os.path.join(data_dir, "options_snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    loader = ScripMasterLoader(data_dir=data_dir)
    rows = loader.download()

    snapshot_path = os.path.join(snapshot_dir, f"{date_str}.json")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"INFO: Saved NFO options snapshot ({len(rows)} contracts) to {snapshot_path}")
    return os.path.abspath(snapshot_path)


def resolve_token(
    symbol: str,
    expiry: str,
    strike: float,
    option_type: str,
    fallback_to_snapshots: bool = True,
    data_dir: str = "./datasets"
) -> Optional[Dict[str, Any]]:
    """
    Resolve a token for an NFO option contract.

    First checks the live ScripMaster. If the contract is not found (likely
    because it has expired), walks backwards through saved snapshots until
    the contract is found.

    Args:
        symbol: Underlying symbol name (e.g., "NIFTY", "BANKNIFTY", "SBIN").
        expiry: Expiry date string (YYYY-MM-DD).
        strike: Strike price.
        option_type: "CE" or "PE".
        fallback_to_snapshots: Whether to search historical snapshots if not in live master.
        data_dir: Root datasets directory.

    Returns:
        Dict with token, lotsize, tick_size, tradingsymbol, or None if not found.
    """
    loader = ScripMasterLoader(data_dir=data_dir)
    contract = loader.get_contract(symbol, expiry, strike, option_type)
    if contract:
        return contract

    if not fallback_to_snapshots:
        return None

    snapshot_dir = os.path.join(data_dir, "options_snapshots")
    if not os.path.isdir(snapshot_dir):
        return None

    # Walk backwards through available snapshots
    files = sorted(os.listdir(snapshot_dir), reverse=True)
    for fname in files:
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(snapshot_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:
            continue

        key = f"{symbol.upper()}|{expiry}|{float(strike)}|{option_type.upper()}"
        for item in rows:
            name = str(item.get("name", "")).upper()
            expiry_raw = item.get("expiry")
            try:
                expiry_iso = datetime.strptime(str(expiry_raw), "%d%b%Y").date().isoformat()
            except Exception:
                expiry_iso = str(expiry_raw)
            try:
                strike_f = float(item.get("strike", 0))
            except Exception:
                strike_f = 0.0
            # Infer option type from tradingsymbol if needed
            opt_type = str(item.get("symbol", "")).upper().split("-")[-1]
            if opt_type not in ("CE", "PE"):
                sym = str(item.get("symbol", "")).upper()
                if sym.endswith("-CE") or sym.endswith("CE"):
                    opt_type = "CE"
                elif sym.endswith("-PE") or sym.endswith("PE"):
                    opt_type = "PE"
                else:
                    continue
            item_key = f"{name}|{expiry_iso}|{strike_f}|{opt_type}"
            if item_key == key:
                return {
                    "token": item.get("token"),
                    "lotsize": item.get("lotsize"),
                    "tick_size": item.get("tick_size"),
                    "tradingsymbol": item.get("symbol"),
                    "name": name,
                    "expiry_date": expiry_iso,
                    "strike": strike_f,
                    "option_type": opt_type,
                    "exch_seg": "NFO",
                    "instrumenttype": item.get("instrumenttype"),
                }

    return None
