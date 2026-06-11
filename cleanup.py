"""
QuantLab Cleanup Utility
========================
Delete downloaded parquet data, backtest logs, and strategy files to free up disk space.

Usage:
    python cleanup.py --help
    python cleanup.py --status                    # Show disk usage
    python cleanup.py --dry-run --all             # Preview what would be deleted
    python cleanup.py --all                       # Delete everything
    python cleanup.py --logs --older-than 7       # Delete logs older than 7 days
    python cleanup.py --parquet --symbol SBIN     # Delete SBIN parquet data
    python cleanup.py --parquet --interval FIVE_MINUTE
    python cleanup.py --strategies                # Delete all strategy .py files
    python cleanup.py --strategies --strategy-id trader  # Delete specific strategy
    python cleanup.py --db-orphans                # Clean DB records with missing log files
    python cleanup.py --vacuum                    # Vacuum SQLite DB to reclaim space
"""

import os
import sys
import json
import argparse
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Add project root to path for importing backend modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_size(path: str) -> int:
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


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_disk_usage() -> Dict[str, Any]:
    """Get disk usage stats for all relevant paths."""
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
        size = get_size(path)
        results[name] = {
            "path": path,
            "size_bytes": size,
            "size_human": format_size(size),
            "exists": os.path.exists(path),
        }
        total += size
    
    results["total"] = {
        "size_bytes": total,
        "size_human": format_size(total),
    }
    return results


def print_status():
    """Print current disk usage status."""
    stats = get_disk_usage()
    print("\n" + "=" * 60)
    print("  QUANTLAB DISK USAGE REPORT")
    print("=" * 60)
    
    for name, info in stats.items():
        if name == "total":
            continue
        status = "[OK]" if info["exists"] else "[MISSING]"
        print(f"  {status} {name:25s} {info['size_human']:>12s}  ({info['path']})")
    
    print("-" * 60)
    print(f"  {'TOTAL':25s} {stats['total']['size_human']:>12s}")
    print("=" * 60 + "\n")


def find_parquet_datasets(symbol: Optional[str] = None, interval: Optional[str] = None) -> List[str]:
    """Find parquet dataset paths matching filters."""
    parquet_dir = "./datasets/parquet"
    if not os.path.exists(parquet_dir):
        return []
    
    matches = []
    for sym in os.listdir(parquet_dir):
        sym_path = os.path.join(parquet_dir, sym)
        if not os.path.isdir(sym_path):
            continue
        
        if symbol and sym.upper() != symbol.upper():
            continue
        
        for iv in os.listdir(sym_path):
            iv_path = os.path.join(sym_path, iv)
            if not os.path.isdir(iv_path):
                continue
            
            if interval and iv.upper() != interval.upper():
                continue
            
            data_file = os.path.join(iv_path, "data.parquet")
            if os.path.exists(data_file):
                matches.append(data_file)
    
    return matches


def find_backtest_logs(run_id: Optional[str] = None, older_than_days: Optional[int] = None) -> List[str]:
    """Find backtest log files matching filters."""
    logs_dir = "./logs"
    if not os.path.exists(logs_dir):
        return []
    
    matches = []
    cutoff = None
    if older_than_days is not None:
        cutoff = datetime.now() - timedelta(days=older_than_days)
    
    for fname in os.listdir(logs_dir):
        if not fname.endswith(".jsonl"):
            continue
        
        if run_id:
            # Exact match or prefix match
            base = fname.replace(".jsonl", "")
            if base.upper() != run_id.upper() and not base.upper().startswith(run_id.upper()):
                continue
        
        fpath = os.path.join(logs_dir, fname)
        
        if cutoff is not None:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime > cutoff:
                continue
        
        matches.append(fpath)
    
    return matches


def delete_parquet_datasets(symbol: Optional[str] = None, interval: Optional[str] = None, 
                           dry_run: bool = False) -> Tuple[int, int]:
    """Delete parquet datasets. Returns (files_deleted, bytes_freed)."""
    targets = find_parquet_datasets(symbol=symbol, interval=interval)
    
    if not targets:
        print("  No parquet datasets found matching criteria.")
        return 0, 0
    
    total_bytes = sum(get_size(f) for f in targets)
    
    print(f"  {'[DRY-RUN]' if dry_run else ''} Found {len(targets)} parquet dataset(s) to delete ({format_size(total_bytes)})")
    
    deleted = 0
    freed = 0
    for fpath in targets:
        size = get_size(fpath)
        print(f"    {'[WOULD DELETE]' if dry_run else '[DELETING]'} {fpath}")
        if not dry_run:
            try:
                os.remove(fpath)
                freed += size
                deleted += 1
                # Remove empty parent directories
                parent = os.path.dirname(fpath)
                if os.path.exists(parent) and not os.listdir(parent):
                    os.rmdir(parent)
                    grandparent = os.path.dirname(parent)
                    if os.path.exists(grandparent) and not os.listdir(grandparent):
                        os.rmdir(grandparent)
            except Exception as e:
                print(f"    [ERROR] Failed to delete {fpath}: {e}")
        else:
            freed += size
            deleted += 1
    
    # Update catalog.json if not dry-run
    if not dry_run:
        catalog_path = "./datasets/catalog.json"
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, "r") as f:
                    catalog = json.load(f)
                
                # Remove entries for deleted datasets
                keys_to_remove = []
                for key, info in catalog.items():
                    cat_symbol = info.get("symbol", "")
                    cat_interval = info.get("interval", "")
                    if symbol and cat_symbol.upper() == symbol.upper():
                        if not interval or cat_interval.upper() == interval.upper():
                            keys_to_remove.append(key)
                    elif not symbol and interval and cat_interval.upper() == interval.upper():
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del catalog[key]
                
                with open(catalog_path, "w") as f:
                    json.dump(catalog, f, indent=2)
                
                print(f"  Updated catalog.json (removed {len(keys_to_remove)} entries)")
            except Exception as e:
                print(f"  [WARN] Could not update catalog.json: {e}")
    
    return deleted, freed


def find_strategy_files(strategy_id: Optional[str] = None) -> List[str]:
    """Find strategy .py files in the strategies directory."""
    strategies_dir = "./strategies"
    if not os.path.exists(strategies_dir):
        return []
    
    matches = []
    for fname in os.listdir(strategies_dir):
        if not fname.endswith(".py"):
            continue
        
        if strategy_id:
            base = fname.replace(".py", "")
            if base.upper() != strategy_id.upper():
                continue
        
        fpath = os.path.join(strategies_dir, fname)
        if os.path.isfile(fpath):
            matches.append(fpath)
    
    return matches


def delete_strategy_files(strategy_id: Optional[str] = None, dry_run: bool = False) -> Tuple[int, int]:
    """Delete strategy .py files. Returns (files_deleted, bytes_freed)."""
    targets = find_strategy_files(strategy_id=strategy_id)
    
    if not targets:
        print("  No strategy files found matching criteria.")
        return 0, 0
    
    total_bytes = sum(get_size(f) for f in targets)
    
    print(f"  {'[DRY-RUN]' if dry_run else ''} Found {len(targets)} strategy file(s) to delete ({format_size(total_bytes)})")
    
    deleted = 0
    freed = 0
    for fpath in targets:
        size = get_size(fpath)
        print(f"    {'[WOULD DELETE]' if dry_run else '[DELETING]'} {os.path.basename(fpath)}")
        if not dry_run:
            try:
                os.remove(fpath)
                freed += size
                deleted += 1
            except Exception as e:
                print(f"    [ERROR] Failed to delete {fpath}: {e}")
        else:
            freed += size
            deleted += 1
    
    return deleted, freed


def clean_strategy_db_orphans(dry_run: bool = False) -> Tuple[int, int]:
    """Clean strategy DB records whose .py files no longer exist. Returns (records_deleted, bytes_freed_estimate)."""
    db_path = "./quantlab.db"
    if not os.path.exists(db_path):
        print("  Database not found.")
        return 0, 0
    
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name FROM strategies"))
            rows = result.fetchall()
            
            orphaned = []
            for row in rows:
                sid, name = row
                # Check if corresponding .py file exists
                py_path = f"./strategies/{name}.py"
                if not os.path.exists(py_path):
                    orphaned.append(sid)
            
            if not orphaned:
                print("  No orphaned strategy records found.")
                return 0, 0
            
            print(f"  {'[DRY-RUN]' if dry_run else ''} Found {len(orphaned)} orphaned strategy record(s) in database")
            
            if not dry_run:
                for sid in orphaned:
                    conn.execute(text("DELETE FROM strategies WHERE id = :id"), {"id": sid})
                    print(f"    [DELETED] Strategy DB record {sid}")
                conn.commit()
            else:
                for sid in orphaned:
                    print(f"    [WOULD DELETE] Strategy DB record {sid}")
            
            freed_estimate = len(orphaned) * 1024
            return len(orphaned), freed_estimate
            
    except ImportError:
        print("  [ERROR] SQLAlchemy not available. Cannot clean strategy DB orphans.")
        return 0, 0
    except Exception as e:
        print(f"  [ERROR] Strategy DB cleanup failed: {e}")
        return 0, 0


def delete_backtest_logs(run_id: Optional[str] = None, older_than_days: Optional[int] = None,
                         dry_run: bool = False) -> Tuple[int, int]:
    """Delete backtest log files. Returns (files_deleted, bytes_freed)."""
    targets = find_backtest_logs(run_id=run_id, older_than_days=older_than_days)
    
    if not targets:
        print("  No backtest logs found matching criteria.")
        return 0, 0
    
    total_bytes = sum(get_size(f) for f in targets)
    
    print(f"  {'[DRY-RUN]' if dry_run else ''} Found {len(targets)} backtest log(s) to delete ({format_size(total_bytes)})")
    
    deleted = 0
    freed = 0
    for fpath in targets:
        size = get_size(fpath)
        print(f"    {'[WOULD DELETE]' if dry_run else '[DELETING]'} {os.path.basename(fpath)}")
        if not dry_run:
            try:
                os.remove(fpath)
                freed += size
                deleted += 1
            except Exception as e:
                print(f"    [ERROR] Failed to delete {fpath}: {e}")
        else:
            freed += size
            deleted += 1
    
    return deleted, freed


def clean_db_orphans(dry_run: bool = False) -> Tuple[int, int]:
    """Clean database records whose log files no longer exist. Returns (records_deleted, bytes_freed_estimate)."""
    db_path = "./quantlab.db"
    if not os.path.exists(db_path):
        print("  Database not found.")
        return 0, 0
    
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        with engine.connect() as conn:
            # Find orphaned records
            result = conn.execute(text("SELECT id, log_file_path FROM backtest_results"))
            rows = result.fetchall()
            
            orphaned = []
            for row in rows:
                run_id, log_path = row
                if not log_path or not os.path.exists(log_path):
                    orphaned.append(run_id)
            
            if not orphaned:
                print("  No orphaned database records found.")
                return 0, 0
            
            print(f"  {'[DRY-RUN]' if dry_run else ''} Found {len(orphaned)} orphaned record(s) in database")
            
            if not dry_run:
                # Delete orphaned records
                for run_id in orphaned:
                    conn.execute(text("DELETE FROM backtest_results WHERE id = :id"), {"id": run_id})
                    print(f"    [DELETED] DB record {run_id}")
                conn.commit()
            else:
                for run_id in orphaned:
                    print(f"    [WOULD DELETE] DB record {run_id}")
            
            # Estimate freed space (rough heuristic: ~2KB per record)
            freed_estimate = len(orphaned) * 2048
            return len(orphaned), freed_estimate
            
    except ImportError:
        print("  [ERROR] SQLAlchemy not available. Cannot clean database orphans.")
        return 0, 0
    except Exception as e:
        print(f"  [ERROR] Database cleanup failed: {e}")
        return 0, 0


def vacuum_database(dry_run: bool = False) -> Tuple[bool, int]:
    """Vacuum SQLite database to reclaim space. Returns (success, bytes_before - bytes_after)."""
    db_path = "./quantlab.db"
    if not os.path.exists(db_path):
        print("  Database not found.")
        return False, 0
    
    size_before = get_size(db_path)
    
    if dry_run:
        print(f"  [DRY-RUN] Would vacuum database ({format_size(size_before)})")
        return True, 0
    
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            conn.commit()
        
        size_after = get_size(db_path)
        freed = size_before - size_after
        print(f"  [VACUUMED] Database: {format_size(size_before)} → {format_size(size_after)} (freed {format_size(freed)})")
        return True, freed
        
    except Exception as e:
        print(f"  [ERROR] Database vacuum failed: {e}")
        return False, 0


def main():
    parser = argparse.ArgumentParser(
        description="QuantLab Cleanup Utility - Free up disk space by deleting downloaded data, backtest logs, and strategy files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status                          Show disk usage
  %(prog)s --dry-run --all                   Preview full cleanup
  %(prog)s --all                             Delete all data, logs, and strategies
  %(prog)s --logs --older-than 7             Delete logs older than 7 days
  %(prog)s --parquet --symbol SBIN           Delete SBIN parquet data
  %(prog)s --parquet --interval ONE_MINUTE   Delete all 1-min datasets
  %(prog)s --strategies                      Delete all strategy .py files
  %(prog)s --strategies --strategy-id trader Delete specific strategy
  %(prog)s --db-orphans --vacuum             Clean DB + reclaim space
        """
    )
    
    # Action flags
    parser.add_argument("--status", action="store_true", help="Show disk usage status and exit")
    parser.add_argument("--all", action="store_true", help="Delete ALL parquet data, backtest logs, AND strategy files")
    parser.add_argument("--parquet", action="store_true", help="Delete parquet datasets")
    parser.add_argument("--logs", action="store_true", help="Delete backtest logs")
    parser.add_argument("--strategies", action="store_true", help="Delete strategy .py files")
    parser.add_argument("--db-orphans", action="store_true", help="Remove DB records with missing log files")
    parser.add_argument("--vacuum", action="store_true", help="Vacuum SQLite database to reclaim space")
    
    # Filters
    parser.add_argument("--symbol", type=str, help="Filter by symbol (e.g., SBIN, RELIANCE)")
    parser.add_argument("--interval", type=str, help="Filter by interval (e.g., ONE_MINUTE, FIVE_MINUTE)")
    parser.add_argument("--run-id", type=str, help="Filter logs by run ID (e.g., B-12345678)")
    parser.add_argument("--strategy-id", type=str, help="Filter strategies by name (e.g., trader, ema_crossover)")
    parser.add_argument("--older-than", type=int, metavar="DAYS", help="Only delete items older than N days")
    
    # Safety
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    # Default to --status if no action specified
    if not any([args.status, args.all, args.parquet, args.logs, args.strategies, args.db_orphans, args.vacuum]):
        args.status = True
    
    if args.status:
        print_status()
        return 0
    
    # Determine what to delete
    delete_parquet = args.all or args.parquet
    delete_logs = args.all or args.logs
    delete_strategies = args.all or args.strategies
    
    # Validate filters
    if args.symbol and not delete_parquet:
        print("[ERROR] --symbol requires --parquet or --all")
        return 1
    if args.interval and not delete_parquet:
        print("[ERROR] --interval requires --parquet or --all")
        return 1
    if args.run_id and not delete_logs:
        print("[ERROR] --run-id requires --logs or --all")
        return 1
    if args.strategy_id and not delete_strategies:
        print("[ERROR] --strategy-id requires --strategies or --all")
        return 1
    if args.older_than and not (delete_logs or delete_parquet):
        print("[ERROR] --older-than requires --logs, --parquet, or --all")
        return 1
    
    # Show current status
    print_status()
    
    # Build summary of operations
    operations = []
    if delete_parquet:
        filters = []
        if args.symbol:
            filters.append(f"symbol={args.symbol}")
        if args.interval:
            filters.append(f"interval={args.interval}")
        if args.older_than:
            filters.append(f"older_than={args.older_than}d")
        op = "Delete parquet datasets" + (f" ({', '.join(filters)})" if filters else " (ALL)")
        operations.append(op)
    
    if delete_logs:
        filters = []
        if args.run_id:
            filters.append(f"run_id={args.run_id}")
        if args.older_than:
            filters.append(f"older_than={args.older_than}d")
        op = "Delete backtest logs" + (f" ({', '.join(filters)})" if filters else " (ALL)")
        operations.append(op)
    
    if delete_strategies:
        op = "Delete strategy files"
        if args.strategy_id:
            op += f" (name={args.strategy_id})"
        else:
            op += " (ALL)"
        operations.append(op)
    
    if args.db_orphans:
        operations.append("Clean orphaned DB records")
    
    if args.vacuum:
        operations.append("Vacuum SQLite database")
    
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\n{'=' * 60}")
    print(f"  CLEANUP MODE: {mode}")
    print(f"  Operations:")
    for op in operations:
        print(f"    - {op}")
    print(f"{'=' * 60}\n")
    
    # Confirmation prompt (unless dry-run or --force)
    if not args.dry_run and not args.force:
        confirm = input("Are you sure? This cannot be undone. Type 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return 0
    
    # Execute
    total_freed = 0
    total_files = 0
    total_records = 0
    
    if delete_parquet:
        print("\n[PARQUET DATASETS]")
        n, freed = delete_parquet_datasets(
            symbol=args.symbol,
            interval=args.interval,
            dry_run=args.dry_run
        )
        total_files += n
        total_freed += freed
    
    if delete_logs:
        print("\n[BACKTEST LOGS]")
        n, freed = delete_backtest_logs(
            run_id=args.run_id,
            older_than_days=args.older_than,
            dry_run=args.dry_run
        )
        total_files += n
        total_freed += freed
    
    if delete_strategies:
        print("\n[STRATEGY FILES]")
        n, freed = delete_strategy_files(
            strategy_id=args.strategy_id,
            dry_run=args.dry_run
        )
        total_files += n
        total_freed += freed
    
    if args.db_orphans:
        print("\n[DATABASE ORPHANS]")
        n, freed = clean_db_orphans(dry_run=args.dry_run)
        total_records += n
        total_freed += freed
    
    if args.vacuum:
        print("\n[DATABASE VACUUM]")
        success, freed = vacuum_database(dry_run=args.dry_run)
        if success:
            total_freed += freed
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"  CLEANUP SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Files deleted:     {total_files}")
    print(f"  DB records cleaned: {total_records}")
    print(f"  Space freed:       {format_size(total_freed)}")
    print(f"{'=' * 60}\n")
    
    if not args.dry_run:
        print_status()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
