"""
Data router: dataset download, catalog, symbol search, active feed.
"""

import os
import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse
from pydantic import BaseModel
import pandas as pd
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.data_service import slice_dataframe_by_date
from backend.services.sizing_service import calculate_suggested_position_size

router = APIRouter(prefix="/api/data", tags=["data"])

# Global symbols cache for autocomplete
_symbol_suggestions: List[Dict[str, str]] = []

# Global active feed key
_active_feed_key: Optional[str] = None


def _load_symbol_suggestions():
    global _symbol_suggestions
    from backend.smartapi import SmartAPIClient
    
    tokens = None
    if SmartAPIClient._tokens_cache is not None:
        tokens = SmartAPIClient._tokens_cache
    else:
        token_path = os.path.join("./datasets", "symbol_tokens.json")
        if not os.path.exists(token_path):
            return
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                tokens = json.load(f)
        except Exception as e:
            print(f"ERROR: Failed to load symbol suggestions from file: {e}")
            return
            
    try:
        seen = set()
        temp = []
        for item in tokens:
            exch = item.get("exch_seg")
            inst_type = item.get("instrumenttype", "")
            if exch in ("NSE", "NFO", "MCX", "BSE", "CDS", "BFO", "NCDEX", "NCO"):
                if not inst_type.startswith("OPT"):
                    symbol = item.get("symbol")
                    name = item.get("name")
                    token = item.get("token")
                    if symbol:
                        sym_key = f"{exch}:{symbol}"
                        if sym_key not in seen:
                            seen.add(sym_key)
                            temp.append({
                                "symbol": sym_key,
                                "name": f"{name} ({exch} - {inst_type or 'EQUITY'})",
                                "token": token,
                            })
        _symbol_suggestions = temp
        print(f"INFO: Loaded {len(_symbol_suggestions)} symbol suggestions into memory.")
    except Exception as e:
        print(f"ERROR: Failed to load symbol suggestions: {e}")


def get_symbol_suggestions() -> List[Dict[str, str]]:
    if not _symbol_suggestions:
        _load_symbol_suggestions()
    return _symbol_suggestions


class DownloadDataRequest(BaseModel):
    symbol: str
    interval: str
    from_date: str
    to_date: str
    totp: Optional[str] = None


def _normalize_download_date(date_str: str, default_time: str) -> str:
    """Append default time if date string has no time component."""
    s = date_str.strip()
    if len(s) <= 10:
        return f"{s} {default_time}"
    return s


@router.post("/download")
def download_data(req: DownloadDataRequest):
    client = SmartAPIManager.get_client()
    if not client or not client.jwt_token:
        client = SmartAPIManager.create_fresh_client()

    if not client.is_configured():
        raise HTTPException(status_code=400, detail="SmartAPI credentials not configured in .env file.")

    if req.totp or not client.jwt_token:
        if not req.totp:
            raise HTTPException(status_code=400, detail="TOTP required for SmartAPI authentication.")
        if not client.connect(totp=req.totp):
            raise HTTPException(status_code=400, detail=f"SmartAPI login failed: {client.last_error}")
        SmartAPIManager.set_client(client)

    # Normalize dates to SmartAPI-compatible format (YYYY-MM-DD HH:MM)
    from_date = _normalize_download_date(req.from_date, "09:15")
    to_date = _normalize_download_date(req.to_date, "15:30")

    # Canonicalize the symbol (e.g. NSE:SBIN-EQ or SBIN)
    from backend.services.data_service import normalize_symbol
    normalized_sym = normalize_symbol(req.symbol, req.interval, client)

    df, is_mock = client.fetch_historical_candles(
        symbol=normalized_sym,
        from_date=from_date,
        to_date=to_date,
        interval=req.interval,
    )
    if df.empty:
        raise HTTPException(status_code=400, detail="No historical data returned from SmartAPI.")

    if is_mock:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{req.symbol}' not found on SmartAPI. Check spelling and use exact exchange symbol (e.g. GODFRYPHLP, not GODFREYPHILLIPS). No mock data was saved.",
        )

    file_path = client.save_dataset_csv(normalized_sym, req.interval, df, is_mock=is_mock)
    catalog = client.load_catalog()
    key = f"{normalized_sym.upper()}_{req.interval.upper()}"

    global _active_feed_key
    _active_feed_key = key

    return {
        "message": "Dataset downloaded and cataloged successfully.",
        "details": catalog.get(key, {}),
        "active_feed": key,
        "catalog": catalog,
        "is_mock": is_mock,
    }


@router.get("/datasets")
def list_datasets():
    client = SmartAPIClient()
    return client.load_catalog()


@router.get("/active")
def get_active_feed():
    return {"active_feed_key": _active_feed_key}


@router.post("/active")
def set_active_feed(req: Dict[str, str]):
    global _active_feed_key
    _active_feed_key = req.get("key")
    return {"status": "success", "active_feed_key": _active_feed_key}


@router.get("/symbols/search")
def search_symbols(q: str):
    if not q:
        return []
    query = q.upper().strip()
    query_no_space = query.replace(" ", "")
    suggestions = get_symbol_suggestions()

    p1, p2, p3 = [], [], []
    for item in suggestions:
        sym = item["symbol"].upper()
        name = item["name"].upper()
        tok = item.get("token", "")
        # Build a bare symbol (e.g. NSE:TATAMOTORS-EQ -> TATAMOTORS)
        bare = sym
        if ":" in bare:
            bare = bare.split(":", 1)[1]
        for suffix in ("-EQ", "-BE", "-FUT"):
            if bare.endswith(suffix):
                bare = bare[:-len(suffix)]
        item["bare_symbol"] = bare

        if query == sym or query == name or query == tok or query == bare:
            p1.append(item)
        elif sym.startswith(query) or name.startswith(query) or bare.startswith(query) or sym.startswith(query_no_space) or bare.startswith(query_no_space):
            p2.append(item)
        elif query in sym or query in name or query in bare or query_no_space in sym.replace(" ", "") or query_no_space in bare:
            p3.append(item)

    p1.sort(key=lambda x: len(x["symbol"]))
    p2.sort(key=lambda x: len(x["symbol"]))
    p3.sort(key=lambda x: len(x["symbol"]))
    return (p1 + p2 + p3)[:15]


@router.get("/datasets/{symbol}/{interval}")
def get_dataset(symbol: str, interval: str):
    client = SmartAPIClient()
    df = client.load_dataset_csv(symbol, interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Dataset not found or empty.")

    # Get is_mock from catalog
    catalog = client.load_catalog()
    key = f"{symbol.upper()}_{interval.upper()}"
    is_mock = False
    if key in catalog:
        is_mock = catalog[key].get("is_mock", False)

    # Format time column for Lightweight Charts compatibility
    try:
        times = pd.to_datetime(df['time'])
        if interval.upper() == "ONE_DAY":
            df['time'] = times.dt.strftime('%Y-%m-%d')
        else:
            if times.dt.tz is None:
                times = times.dt.tz_localize('Asia/Kolkata')
            else:
                times = times.dt.tz_convert('Asia/Kolkata')
            naive_times = times.dt.tz_localize(None)
            df['time'] = naive_times.astype('datetime64[s]').astype('int64')
    except Exception as e:
        print(f"DEBUG: Date formatting error for {symbol}: {e}")

    # Suggested max position size
    suggested = calculate_suggested_position_size(
        price_series=df['close'].iloc[-100:],
        initial_capital=100000.0,
        trade_type="INTRADAY",
    )

    data = df.to_dict(orient="records")
    return {
        "symbol": symbol.upper(),
        "interval": interval.upper(),
        "total_records": len(df),
        "suggested_max_position": suggested,
        "is_mock": is_mock,
        "candles": data[:2000],
    }


@router.get("/download-file/{symbol}/{interval}")
def download_file(symbol: str, interval: str):
    """Serve a stored CSV or Excel dataset as a file download."""
    client = SmartAPIClient()
    catalog = client.load_catalog()
    key = f"{symbol.upper()}_{interval.upper()}"
    if key not in catalog:
        raise HTTPException(status_code=404, detail="Dataset not found in catalog.")
    
    file_path = catalog[key].get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")
    
    filename = os.path.basename(file_path)
    return FileResponse(file_path, filename=filename, media_type="text/csv")

