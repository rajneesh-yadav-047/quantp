"""
Async download job service.

Manages long-running historical data downloads in background threads,
tracking progress in the SQLite database so the frontend can poll for status.
"""

import time
import json
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from backend.database import SessionLocal, DownloadJobDB
from backend.smartapi import SmartAPIClient
from backend.services.data_aggregator import aggregate_data, get_interval_metadata
from backend.services.smartapi_manager import SmartAPIManager

# ── Worker pool ──
# We use a single background thread to serialise downloads so we don't
# hammer SmartAPI with concurrent requests.  If you want parallelism
# you can increase max_workers, but be mindful of Angel One rate limits.
_download_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="download_")

# ── In-memory job cache for fast polling (avoids DB hits every 2 s) ──
_job_cache: Dict[str, dict] = {}


def _get_db() -> Session:
    return SessionLocal()


def _update_cache(job: DownloadJobDB):
    """Sync a job row into the in-memory cache for fast polling."""
    _job_cache[job.id] = {
        "id": job.id,
        "symbol": job.symbol,
        "interval": job.interval,
        "start_date": job.start_date,
        "end_date": job.end_date,
        "status": job.status,
        "progress": job.progress,
        "total_chunks": job.total_chunks,
        "completed_chunks": job.completed_chunks,
        "records_downloaded": job.records_downloaded,
        "error_message": job.error_message,
        "file_path": job.file_path,
        "catalog_key": job.catalog_key,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


# ── Public helpers ──

def get_job(job_id: str) -> Optional[dict]:
    """Return cached job status or load from DB."""
    if job_id in _job_cache:
        return _job_cache[job_id]
    db = _get_db()
    try:
        job = db.query(DownloadJobDB).filter(DownloadJobDB.id == job_id).first()
        if job:
            _update_cache(job)
            return _job_cache[job_id]
    finally:
        db.close()
    return None


def list_jobs(limit: int = 50) -> List[dict]:
    """Return recent jobs, newest first."""
    db = _get_db()
    try:
        rows = (
            db.query(DownloadJobDB)
            .order_by(DownloadJobDB.created_at.desc())
            .limit(limit)
            .all()
        )
        for row in rows:
            _update_cache(row)
        return [_job_cache[r.id] for r in rows]
    finally:
        db.close()


def _sync_job(job_id: str, status: str, progress: int = None, completed_chunks: int = None,
              total_chunks: int = None, records_downloaded: int = None, error_message: str = None,
              file_path: str = None, catalog_key: str = None):
    """Flush job updates to DB + cache."""
    db = _get_db()
    try:
        job = db.query(DownloadJobDB).filter(DownloadJobDB.id == job_id).first()
        if not job:
            return
        job.status = status
        if progress is not None:
            job.progress = progress
        if completed_chunks is not None:
            job.completed_chunks = completed_chunks
        if total_chunks is not None:
            job.total_chunks = total_chunks
        if records_downloaded is not None:
            job.records_downloaded = records_downloaded
        if error_message is not None:
            job.error_message = error_message
        if file_path is not None:
            job.file_path = file_path
        if catalog_key is not None:
            job.catalog_key = catalog_key
        job.updated_at = datetime.utcnow()
        db.commit()
        _update_cache(job)
    finally:
        db.close()


# ── Chunk-limits (mirror aggregator) ──
_CHUNK_LIMITS: Dict[str, int] = {
    "ONE_MINUTE": 30,
    "FIVE_MINUTE": 60,
    "FIFTEEN_MINUTE": 60,
    "THIRTY_MINUTE": 60,
    "ONE_HOUR": 120,
    "ONE_DAY": 2000,
    "ONE_WEEK": 2000,
    "ONE_MONTH": 2000,
}


def _count_chunks(interval: str, start_date: str, end_date: str) -> int:
    """Estimate how many API chunks a range will need."""
    from datetime import datetime as _dt
    chunk_days = _CHUNK_LIMITS.get(interval.upper(), 60)
    start = _dt.strptime(start_date, "%Y-%m-%d")
    end = _dt.strptime(end_date, "%Y-%m-%d")
    total_days = (end - start).days + 1
    return max(1, (total_days + chunk_days - 1) // chunk_days)


# ── Async threshold ──
# Date ranges that need more than this many chunks will be forced to async.
_ASYNC_THRESHOLD_CHUNKS = 5


def should_be_async(interval: str, start_date: str, end_date: str) -> bool:
    """Return True if a range is big enough to warrant background processing."""
    return _count_chunks(interval, start_date, end_date) > _ASYNC_THRESHOLD_CHUNKS


# ── Background worker ──

def _run_download_job(job_id: str, symbol: str, interval: str, start_date: str, end_date: str):
    """Worker function executed in the thread pool."""
    import traceback
    try:
        _run_download_job_inner(job_id, symbol, interval, start_date, end_date)
    except Exception as e:
        print(f"CRITICAL: Job {job_id} crashed with unhandled exception: {e}")
        traceback.print_exc()
        _sync_job(job_id, status="failed", error_message=f"Internal crash: {str(e)}", progress=0)


def _run_download_job_inner(job_id: str, symbol: str, interval: str, start_date: str, end_date: str):
    """Inner worker — all exceptions are caught by the outer wrapper."""
    print(f"[Job {job_id}] Starting download: {symbol} {interval} {start_date} -> {end_date}")
    _sync_job(job_id, status="running", progress=0)

    # Ensure we have a logged-in client
    print(f"[Job {job_id}] Getting SmartAPI client...")
    client = SmartAPIManager.get_client()
    print(f"[Job {job_id}] Client from manager: {client}")
    if not client or not client.jwt_token:
        print(f"[Job {job_id}] Client not authenticated, creating fresh client...")
        client = SmartAPIManager.create_fresh_client()
    if not client or not client.jwt_token:
        print(f"[Job {job_id}] Still no JWT, attempting connect...")
        if not client.connect():
            _sync_job(
                job_id,
                status="failed",
                error_message=f"SmartAPI login failed: {client.last_error}",
                progress=0,
            )
            print(f"[Job {job_id}] Connect failed: {client.last_error}")
            return
        SmartAPIManager.set_client(client)
    print(f"[Job {job_id}] Client authenticated. JWT present: {bool(client.jwt_token)}")

    # Canonicalize symbol
    print(f"[Job {job_id}] Normalizing symbol...")
    from backend.services.data_service import normalize_symbol
    normalized_sym = normalize_symbol(symbol, interval, client)
    print(f"[Job {job_id}] Normalized symbol: {normalized_sym}")

    total_chunks = _count_chunks(interval, start_date, end_date)
    print(f"[Job {job_id}] Total chunks: {total_chunks}")
    _sync_job(job_id, status="running", total_chunks=total_chunks, progress=0)

    # Use the aggregator with progress hooks
    print(f"[Job {job_id}] Starting aggregation...")
    try:
        df, status = _aggregate_with_progress(
            job_id=job_id,
            symbol=normalized_sym,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            client=client,
        )
    except Exception as e:
        print(f"[Job {job_id}] ERROR in _aggregate_with_progress: {e}")
        import traceback
        traceback.print_exc()
        _sync_job(job_id, status="failed", error_message=str(e), progress=0)
        return

    print(f"[Job {job_id}] Aggregation done. df={df is not None}, status={status}")

    if df is None or df.empty:
        print(f"[Job {job_id}] No data returned.")
        _sync_job(
            job_id,
            status="failed",
            error_message="No historical data returned from SmartAPI.",
            progress=0,
        )
        return

    if status == "mock":
        print(f"[Job {job_id}] Mock data returned.")
        _sync_job(
            job_id,
            status="failed",
            error_message=f"Symbol '{symbol}' not found on SmartAPI. No mock data was saved.",
            progress=0,
        )
        return

    # Save to CSV and update catalog
    print(f"[Job {job_id}] Saving to CSV...")
    try:
        file_path = client.save_dataset_csv(normalized_sym, interval, df, is_mock=False)
        catalog = client.load_catalog()
        key = f"{normalized_sym.upper()}_{interval.upper()}"

        meta = get_interval_metadata(df, interval)
        catalog_entry = catalog.get(key, {})
        catalog_entry.update(meta)
        catalog[key] = catalog_entry
        with open(client.catalog_path, "w") as f:
            json.dump(catalog, f, indent=2)

        print(f"[Job {job_id}] Saved to {file_path}. Records: {len(df)}")
        _sync_job(
            job_id,
            status="completed",
            progress=100,
            records_downloaded=len(df),
            file_path=file_path,
            catalog_key=key,
        )
    except Exception as e:
        print(f"[Job {job_id}] ERROR saving CSV: {e}")
        import traceback
        traceback.print_exc()
        _sync_job(job_id, status="failed", error_message=str(e), progress=0)


def _aggregate_with_progress(
    job_id: str,
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    client: SmartAPIClient,
) -> tuple:
    """
    Wrapper around aggregate_data that injects progress updates after each chunk.

    We re-implement the core chunking loop here so we can call _sync_job after
    every successful chunk.
    """
    import math
    from backend.services.data_aggregator import (
        _parse_date_str, _to_date_str, _chunk_size_days, _merge_chunks,
        _slice_exact_range, _validate_and_fill
    )

    interval = interval.upper()
    chunk_days = _chunk_size_days(interval)
    start_dt = _parse_date_str(start_date)
    end_dt = _parse_date_str(end_date)

    total_chunks = _count_chunks(interval, start_date, end_date)
    chunks = []
    chunk_start = start_dt
    completed = 0

    print(f"[Job {job_id}] _aggregate_with_progress: {total_chunks} chunks, interval={interval}, chunk_days={chunk_days}")

    while chunk_start <= end_dt:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_dt)
        from_str = f"{_to_date_str(chunk_start)} 09:15"
        to_str = f"{_to_date_str(chunk_end)} 15:30"

        print(f"[Job {job_id}] Chunk {completed+1}/{total_chunks}: {from_str} -> {to_str}")

        try:
            import time as _time
            t0 = _time.time()
            df_chunk, is_mock = client.fetch_historical_candles(symbol, from_str, to_str, interval)
            elapsed = _time.time() - t0
            print(f"[Job {job_id}] Chunk {completed+1} done in {elapsed:.1f}s. is_mock={is_mock}, rows={len(df_chunk) if df_chunk is not None else 0}")
        except Exception as e:
            print(f"[Job {job_id}] Chunk {completed+1} EXCEPTION: {e}")
            df_chunk, is_mock = None, False

        if is_mock:
            print(f"[Job {job_id}] Mock data on chunk {completed+1}. Aborting.")
            break

        if df_chunk is not None and not df_chunk.empty:
            chunks.append(df_chunk)
            completed += 1
        else:
            # Empty chunk counts as completed (no data for that period)
            completed += 1

        # Update progress
        progress = int((completed / total_chunks) * 100)
        print(f"[Job {job_id}] Progress: {progress}% ({completed}/{total_chunks})")
        _sync_job(job_id, status="running", completed_chunks=completed, progress=progress)

        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(0.3)  # rate-limit padding

    print(f"[Job {job_id}] Loop finished. chunks collected={len(chunks)}")

    if not chunks:
        return None, "failed"

    merged = _merge_chunks(chunks)
    if merged is None or merged.empty:
        return None, "failed"

    merged = _slice_exact_range(merged, start_dt, end_dt)
    if merged is None or merged.empty:
        return None, "failed"

    merged, gaps_info = _validate_and_fill(merged, interval)
    status = "partial" if gaps_info else "ok"
    print(f"[Job {job_id}] Final status: {status}, rows={len(merged)}")
    return merged, status


# ── Public API ──

def enqueue_download(symbol: str, interval: str, start_date: str, end_date: str) -> str:
    """Create a new download job and submit it to the background worker."""
    db = _get_db()
    try:
        job = DownloadJobDB(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            status="pending",
            total_chunks=_count_chunks(interval, start_date, end_date),
        )
        db.add(job)
        db.commit()
        job_id = job.id
        _update_cache(job)
    finally:
        db.close()

    _download_executor.submit(
        _run_download_job, job_id, symbol, interval, start_date, end_date
    )
    return job_id


def cancel_job(job_id: str) -> bool:
    """Mark a pending job as cancelled."""
    db = _get_db()
    try:
        job = db.query(DownloadJobDB).filter(DownloadJobDB.id == job_id).first()
        if job and job.status == "pending":
            job.status = "cancelled"
            job.updated_at = datetime.utcnow()
            db.commit()
            _update_cache(job)
            return True
    finally:
        db.close()
    return False


def cleanup_old_jobs(max_age_hours: int = 48):
    """Delete completed/failed jobs older than max_age_hours."""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    db = _get_db()
    try:
        db.query(DownloadJobDB).filter(
            DownloadJobDB.status.in_(["completed", "failed", "cancelled"]),
            DownloadJobDB.updated_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
