"""
Data router: dataset download, catalog, symbol search, active feed.
"""

import os
import json
from datetime import datetime as _dt
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse
from pydantic import BaseModel
import pandas as pd
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.data_service import slice_dataframe_by_date
from backend.services.data_aggregator import aggregate_data, get_interval_metadata
from backend.services.sizing_service import calculate_suggested_position_size
from backend.services import download_job_service as djs

router = APIRouter(prefix="/api/data", tags=["data"])

# Global symbols cache for autocomplete
_symbol_suggestions: List[Dict[str, str]] = []

# Global active feed key
_active_feed_key: Optional[str] = None


# ── Async thresholds ──
# If a request needs more chunks than this, we force async background processing.
_ASYNC_CHUNK_THRESHOLD = 5


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
    force_async: bool = False


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

    # Use the universal aggregator for large date ranges (chunks SmartAPI requests)
    raw_from = req.from_date.strip()[:10]
    raw_to = req.to_date.strip()[:10]

    # Validate date format
    try:
        start_dt = _dt.strptime(raw_from, "%Y-%m-%d")
        end_dt = _dt.strptime(raw_to, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Determine whether to run async (background) or sync (inline)
    chunk_count = djs._count_chunks(req.interval, raw_from, raw_to)
    use_async = req.force_async or chunk_count > _ASYNC_CHUNK_THRESHOLD

    if use_async:
        # Enqueue a background job and return immediately
        job_id = djs.enqueue_download(req.symbol, req.interval, raw_from, raw_to)
        return {
            "message": "Download job queued. Poll /download/jobs/{job_id} for status.",
            "job_id": job_id,
            "status": "queued",
            "chunks": chunk_count,
        }

    # ── Synchronous path (small ranges) ──
    # Canonicalize the symbol
    from backend.services.data_service import normalize_symbol
    normalized_sym = normalize_symbol(req.symbol, req.interval, client)

    try:
        df, status = aggregate_data(
            symbol=normalized_sym,
            interval=req.interval,
            start_date=raw_from,
            end_date=raw_to,
            client=client,
        )
    except Exception as e:
        print(f"ERROR: aggregate_data failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="No historical data returned from SmartAPI.")

    if status == "mock":
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{req.symbol}' not found on SmartAPI. Check spelling and use exact exchange symbol (e.g. GODFRYPHLP, not GODFREYPHILLIPS). No mock data was saved.",
        )

    file_path = client.save_dataset_csv(normalized_sym, req.interval, df, is_mock=False)
    catalog = client.load_catalog()
    key = f"{normalized_sym.upper()}_{req.interval.upper()}"

    # Add interval metadata to catalog entry
    meta = get_interval_metadata(df, req.interval)
    catalog_entry = catalog.get(key, {})
    catalog_entry.update(meta)
    catalog[key] = catalog_entry
    with open(client.catalog_path, "w") as f:
        json.dump(catalog, f, indent=2)

    global _active_feed_key
    _active_feed_key = key

    return {
        "message": "Dataset downloaded and cataloged successfully.",
        "details": catalog.get(key, {}),
        "active_feed": key,
        "catalog": catalog,
        "status": status,
    }


@router.get("/download/jobs")
def list_download_jobs(limit: int = 50):
    """Return recent download jobs, newest first."""
    return {"jobs": djs.list_jobs(limit=limit)}


@router.get("/download/jobs/{job_id}")
def get_download_job(job_id: str):
    """Get status of a single download job."""
    job = djs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/download/jobs/{job_id}/cancel")
def cancel_download_job(job_id: str):
    """Cancel a pending download job."""
    ok = djs.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Job not found or already running/completed.")
    return {"message": "Job cancelled.", "job_id": job_id}


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

