"""
Options Collector Service: APScheduler-based daily background job that
snapshots the NFO ScripMaster and downloads 1-minute candles for all
contracts expiring on the current trading day.

Runs every weekday at 15:31 IST, after market close but before the
expired contracts are removed from the live ScripMaster file.
"""

import os
import time
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager
from engine.options_catalog import ScripMasterLoader, save_daily_snapshot
from engine.options_data import OptionsDataManager


class OptionsCollectorService:
    """
    Manages the APScheduler job for daily options data collection.
    """

    def __init__(self, data_dir: str = "./datasets"):
        self.data_dir = data_dir
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._job_id = "options_daily_collector"

    def start(self) -> None:
        """Start the APScheduler with the daily collector job."""
        if self.scheduler and self.scheduler.running:
            print("INFO: OptionsCollectorService already running.")
            return

        self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        self.scheduler.add_job(
            self._daily_job,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=15,
                minute=31,
            ),
            id=self._job_id,
            replace_existing=True,
            misfire_grace_time=3600,  # Allow up to 1 hour late start
        )
        self.scheduler.start()
        print("INFO: OptionsCollectorService started. Job fires Mon-Fri at 15:31 IST.")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("INFO: OptionsCollectorService stopped.")

    def _ensure_authenticated(self) -> bool:
        """Ensure SmartAPI client has a valid JWT, refreshing if needed."""
        client = SmartAPIManager.get_client()
        if client and client.jwt_token:
            # Attempt a lightweight refresh to extend validity
            if client.refresh_session():
                return True
            # Refresh may fail if token is truly expired; try full re-auth
            # if we have a stored TOTP generator in environment
            totp = os.getenv("SMARTAPI_TOTP")
            if totp and client.connect(totp=totp):
                SmartAPIManager.set_client(client)
                return True
            print("WARN: SmartAPI client JWT expired and re-auth failed.")
            return False

        # No client at all — create fresh and attempt login with env TOTP
        client = SmartAPIManager.create_fresh_client()
        totp = os.getenv("SMARTAPI_TOTP")
        if totp and client.connect(totp=totp):
            SmartAPIManager.set_client(client)
            return True

        print("WARN: No authenticated SmartAPI client available. Skipping options collection.")
        return False

    def _daily_job(self) -> None:
        """Main job: snapshot ScripMaster, find expiring contracts, download data."""
        print(f"INFO: Options daily collector job started at {datetime.now().isoformat()}")

        if not self._ensure_authenticated():
            return

        today = date.today().isoformat()
        try:
            snapshot_path = save_daily_snapshot(today, data_dir=self.data_dir)
            print(f"INFO: Snapshot saved: {snapshot_path}")
        except Exception as e:
            print(f"ERROR: Failed to save daily snapshot: {e}")
            return

        loader = ScripMasterLoader(data_dir=self.data_dir)
        try:
            loader.download()
            expiring = loader.contracts_expiring_on(today)
        except Exception as e:
            print(f"ERROR: Failed to load ScripMaster or find expiring contracts: {e}")
            return

        if not expiring:
            print(f"INFO: No NFO options expiring today ({today}).")
            return

        print(f"INFO: Found {len(expiring)} contracts expiring today. Starting download...")
        manager = OptionsDataManager(data_dir=self.data_dir)
        from_dt = f"{today} 09:15"
        to_dt = f"{today} 15:30"

        success_count = 0
        fail_count = 0
        for item in expiring:
            try:
                name = str(item.get("name", "")).strip()
                expiry = item.get("expiry")
                try:
                    expiry_iso = datetime.strptime(str(expiry), "%d%b%Y").date().isoformat()
                except Exception:
                    expiry_iso = str(expiry)
                strike = float(item.get("strike", 0))
                option_type = str(item.get("symbol", "")).upper().split("-")[-1]
                if option_type not in ("CE", "PE"):
                    sym = str(item.get("symbol", "")).upper()
                    if sym.endswith("-CE") or sym.endswith("CE"):
                        option_type = "CE"
                    elif sym.endswith("-PE") or sym.endswith("PE"):
                        option_type = "PE"
                    else:
                        continue
                token = item.get("token")
                lotsize = item.get("lotsize", 1)
                tradingsymbol = item.get("symbol")

                if not token or not name or not expiry_iso:
                    continue

                result = manager.fetch_and_store(
                    token=token,
                    tradingsymbol=tradingsymbol or name,
                    expiry=expiry_iso,
                    strike=strike,
                    option_type=option_type,
                    lotsize=lotsize,
                    from_dt=from_dt,
                    to_dt=to_dt,
                )
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"ERROR: Failed to download options data for {item.get('symbol')}: {e}")
                fail_count += 1

        print(
            f"INFO: Options daily collector job finished. "
            f"Success: {success_count}, Failed: {fail_count}, Total: {len(expiring)}"
        )


# Global singleton instance
_options_collector_service: Optional[OptionsCollectorService] = None


def get_options_collector_service() -> OptionsCollectorService:
    """Return the global OptionsCollectorService singleton."""
    global _options_collector_service
    if _options_collector_service is None:
        _options_collector_service = OptionsCollectorService()
    return _options_collector_service
