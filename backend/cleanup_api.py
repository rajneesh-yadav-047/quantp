"""
Cleanup API endpoints for QuantLab Backend.
Provides REST API access to disk space management operations.
"""

import os
import json
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


def _get_size(path: str) -> int:
    """Get total size in bytes for a file or directory."""
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


class CleanupStatusResponse(BaseModel):
    datasets_parquet: Dict[str, Any]
    logs: Dict[str, Any]
    strategies: Dict[str, Any]
    database: Dict[str, Any]
    backend_log: Dict[str, Any]
    backend_restart_log: Dict[str, Any]
    frontend_dev_log: Dict[str, Any]
    total_bytes: int
    total_human: str


class CleanupRequest(BaseModel):
    target: str  # "parquet", "logs", "strategies", "db_orphans", "all"
    symbol: Optional[str] = None
    interval: Optional[str] = None
    run_id: Optional[str] = None
    strategy_id: Optional[str] = None
    older_than_days: Optional[int] = None
    dry_run: bool = True


class CleanupResult(BaseModel):
    success: bool
    dry_run: bool
    files_deleted: int
    bytes_freed: int
    bytes_freed_human: str
    details: List[str]


@router.get("/status", response_model=CleanupStatusResponse)
def cleanup_status():
    """Get current disk usage for all data directories."""
    paths = {
        "datasets_parquet": "./datasets/parquet",
        "logs": "./logs",
        "strategies": "./strategies",
        "database": "./quantlab.db",
        "backend_log": "./backend.log",
        "backend_restart_log": "./backend-restart.log",
        "frontend_dev_log": "./frontend-dev.log",
    }

    results = {}
    total = 0
    for name, path in paths.items():
        size = _get_size(path)
        results[name] = {
            "path": path,
            "size_bytes": size,
            "size_human": _format_size(size),
            "exists": os.path.exists(path),
        }
        total += size

    return CleanupStatusResponse(
        **results,
        total_bytes=total,
        total_human=_format_size(total),
    )


@router.post("/run", response_model=CleanupResult)
def run_cleanup(req: CleanupRequest):
    """Run cleanup operation on parquet data, logs, or database orphans."""
    details = []
    files_deleted = 0
    bytes_freed = 0

    if req.target in ("parquet", "all"):
        # Find and delete parquet datasets
        parquet_dir = "./datasets/parquet"
        if os.path.exists(parquet_dir):
            for sym in os.listdir(parquet_dir):
                sym_path = os.path.join(parquet_dir, sym)
                if not os.path.isdir(sym_path):
                    continue
                if req.symbol and sym.upper() != req.symbol.upper():
                    continue

                for iv in os.listdir(sym_path):
                    iv_path = os.path.join(sym_path, iv)
                    if not os.path.isdir(iv_path):
                        continue
                    if req.interval and iv.upper() != req.interval.upper():
                        continue

                    data_file = os.path.join(iv_path, "data.parquet")
                    if os.path.exists(data_file):
                        # Check age filter
                        if req.older_than_days is not None:
                            mtime = datetime.fromtimestamp(os.path.getmtime(data_file))
                            if mtime > datetime.now() - timedelta(days=req.older_than_days):
                                continue

                        size = _get_size(data_file)
                        if req.dry_run:
                            details.append(f"[WOULD DELETE] parquet: {sym}/{iv}/data.parquet ({_format_size(size)})")
                        else:
                            try:
                                os.remove(data_file)
                                files_deleted += 1
                                bytes_freed += size
                                details.append(f"[DELETED] parquet: {sym}/{iv}/data.parquet ({_format_size(size)})")
                                # Clean empty dirs
                                if not os.listdir(iv_path):
                                    os.rmdir(iv_path)
                                if not os.listdir(sym_path):
                                    os.rmdir(sym_path)
                            except Exception as e:
                                details.append(f"[ERROR] Failed to delete {data_file}: {e}")

            # Update catalog if not dry-run
            if not req.dry_run:
                catalog_path = "./datasets/catalog.json"
                if os.path.exists(catalog_path):
                    try:
                        with open(catalog_path, "r") as f:
                            catalog = json.load(f)
                        keys_to_remove = []
                        for key, info in catalog.items():
                            cat_symbol = info.get("symbol", "")
                            cat_interval = info.get("interval", "")
                            match = False
                            if req.symbol and cat_symbol.upper() == req.symbol.upper():
                                if not req.interval or cat_interval.upper() == req.interval.upper():
                                    match = True
                            elif not req.symbol and req.interval and cat_interval.upper() == req.interval.upper():
                                match = True
                            elif not req.symbol and not req.interval:
                                match = True
                            if match:
                                keys_to_remove.append(key)
                        for key in keys_to_remove:
                            del catalog[key]
                        with open(catalog_path, "w") as f:
                            json.dump(catalog, f, indent=2)
                        details.append(f"Updated catalog.json (removed {len(keys_to_remove)} entries)")
                    except Exception as e:
                        details.append(f"[WARN] Could not update catalog.json: {e}")

    if req.target in ("logs", "all"):
        # Find and delete backtest logs
        logs_dir = "./logs"
        if os.path.exists(logs_dir):
            for fname in os.listdir(logs_dir):
                if not fname.endswith(".jsonl"):
                    continue
                if req.run_id:
                    base = fname.replace(".jsonl", "")
                    if base.upper() != req.run_id.upper() and not base.upper().startswith(req.run_id.upper()):
                        continue

                fpath = os.path.join(logs_dir, fname)

                # Check age filter
                if req.older_than_days is not None:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime > datetime.now() - timedelta(days=req.older_than_days):
                        continue

                size = _get_size(fpath)
                if req.dry_run:
                    details.append(f"[WOULD DELETE] log: {fname} ({_format_size(size)})")
                else:
                    try:
                        os.remove(fpath)
                        files_deleted += 1
                        bytes_freed += size
                        details.append(f"[DELETED] log: {fname} ({_format_size(size)})")
                    except Exception as e:
                        details.append(f"[ERROR] Failed to delete {fpath}: {e}")

    if req.target in ("strategies", "all"):
        # Find and delete strategy .py files
        strategies_dir = "./strategies"
        if os.path.exists(strategies_dir):
            for fname in os.listdir(strategies_dir):
                if not fname.endswith(".py"):
                    continue
                if req.strategy_id:
                    base = fname.replace(".py", "")
                    if base.upper() != req.strategy_id.upper():
                        continue

                fpath = os.path.join(strategies_dir, fname)
                size = _get_size(fpath)
                if req.dry_run:
                    details.append(f"[WOULD DELETE] strategy: {fname} ({_format_size(size)})")
                else:
                    try:
                        os.remove(fpath)
                        files_deleted += 1
                        bytes_freed += size
                        details.append(f"[DELETED] strategy: {fname} ({_format_size(size)})")
                    except Exception as e:
                        details.append(f"[ERROR] Failed to delete {fpath}: {e}")

            # Clean orphaned strategy DB records if not dry-run
            if not req.dry_run:
                db_path = "./quantlab.db"
                if os.path.exists(db_path):
                    try:
                        from sqlalchemy import create_engine, text
                        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
                        with engine.connect() as conn:
                            result = conn.execute(text("SELECT id, name FROM strategies"))
                            rows = result.fetchall()
                            orphaned = []
                            for row in rows:
                                sid, name = row
                                py_path = f"./strategies/{name}.py"
                                if not os.path.exists(py_path):
                                    orphaned.append(sid)
                            if orphaned:
                                for sid in orphaned:
                                    conn.execute(text("DELETE FROM strategies WHERE id = :id"), {"id": sid})
                                    details.append(f"[DELETED] Strategy DB orphan: {sid}")
                                conn.commit()
                                details.append(f"Cleaned {len(orphaned)} orphaned strategy DB record(s)")
                    except Exception as e:
                        details.append(f"[WARN] Could not clean strategy DB orphans: {e}")

    if req.target in ("db_orphans", "all"):
        # Clean database records with missing log files
        db_path = "./quantlab.db"
        if os.path.exists(db_path):
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT id, log_file_path FROM backtest_results"))
                    rows = result.fetchall()
                    orphaned = []
                    for row in rows:
                        run_id, log_path = row
                        if not log_path or not os.path.exists(log_path):
                            orphaned.append(run_id)

                    if orphaned:
                        if req.dry_run:
                            for run_id in orphaned:
                                details.append(f"[WOULD DELETE] DB orphan: {run_id}")
                        else:
                            for run_id in orphaned:
                                conn.execute(text("DELETE FROM backtest_results WHERE id = :id"), {"id": run_id})
                                details.append(f"[DELETED] DB orphan: {run_id}")
                            conn.commit()
                        details.append(f"{'Would clean' if req.dry_run else 'Cleaned'} {len(orphaned)} orphaned DB record(s)")
                    else:
                        details.append("No orphaned DB records found")
            except Exception as e:
                details.append(f"[ERROR] DB orphan cleanup failed: {e}")

    return CleanupResult(
        success=True,
        dry_run=req.dry_run,
        files_deleted=files_deleted,
        bytes_freed=bytes_freed,
        bytes_freed_human=_format_size(bytes_freed),
        details=details,
    )


@router.post("/vacuum")
def vacuum_database(dry_run: bool = True):
    """Vacuum SQLite database to reclaim freed space."""
    db_path = "./quantlab.db"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found")

    size_before = _get_size(db_path)

    if dry_run:
        return {
            "dry_run": True,
            "size_before_human": _format_size(size_before),
            "message": "Would vacuum database",
        }

    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            conn.commit()

        size_after = _get_size(db_path)
        freed = size_before - size_after
        return {
            "dry_run": False,
            "size_before_human": _format_size(size_before),
            "size_after_human": _format_size(size_after),
            "freed_human": _format_size(freed),
            "freed_bytes": freed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vacuum failed: {str(e)}")
