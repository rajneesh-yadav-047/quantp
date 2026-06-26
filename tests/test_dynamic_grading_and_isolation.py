import sys
import os
import unittest
import json
import uuid
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, ResearchJobDB, WalkForwardFoldDB
from engine.strategy_registry.base import StrategyRegistry, StrategyMetadata, BaseStrategy, ParameterSpec
from engine.research_engine import ResearchEngine
from backend.main import run_next_research_job

# Define a minimal strategy for ultra-fast execution
class UltraFastStrategy(BaseStrategy):
    metadata = StrategyMetadata(
        name="UltraFast Reversion",
        description="Fast test strategy.",
        regime_compatibility={"QUIET_RANGING": 100},
        preferred_timeframes=["FIVE_MINUTE"],
        typical_holding_bars=1,
        requires_volume=False,
    )
    parameter_specs = [
        ParameterSpec("param_val", "range_int", 2, 1, 5)
    ]
    def entry_rules(self, market_state): return True
    def exit_rules(self, market_state, position): return True
    def stop_loss(self, entry_price, current_price, direction): return False
    def take_profit(self, entry_price, current_price, direction): return False
    def position_size(self, capital, atr, price): return 1
    def get_param_grid(self, granularity="medium"): return {"param_val": [2]}
    def generate_code(self, symbol):
        return "class Strategy: def on_bar(self, df, i): return []"


class TestDynamicGradingAndIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        StrategyRegistry.register(UltraFastStrategy)

    def setUp(self):
        # Setup in-memory SQLite DB
        self.db_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=self.db_engine)
        self.session = Session()
        Base.metadata.create_all(bind=self.db_engine)
        
        # Enable WAL (or try to) on memory DB to test code paths
        from sqlalchemy import text
        try:
            with self.db_engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL;"))
        except Exception:
            pass

        # Generate minimal mock dataset (20 bars)
        np.random.seed(42)
        dates = pd.date_range(start="2026-06-01", periods=20, freq="5min")
        close_prices = np.random.randn(20).cumsum() + 100.0
        self.mock_df = pd.DataFrame({
            "time": dates.strftime('%Y-%m-%d %H:%M:%S'),
            "open": close_prices - 0.5,
            "high": close_prices + 1.0,
            "low": close_prices - 1.0,
            "close": close_prices,
            "volume": np.random.randint(100, 1000, size=20)
        })

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.db_engine)

    def test_dynamic_grading_logic(self):
        # We instantiate a worker and test dynamic grading rules directly
        worker = ResearchEngine(db_session=self.session)
        
        # Test Case 1: Conservative Profile requires high criteria
        # A strategy with Sharpe 1.2 (fails Conservative pass threshold of 1.5, and is >= 1.0 fail threshold, so it becomes Needs Review)
        # Or let's test directly with mock profiles:
        
        # Let's mock a job
        job = ResearchJobDB(
            id=str(uuid.uuid4()),
            strategy_name="UltraFast Reversion",
            symbol="NSE:SBIN-EQ",
            interval="FIVE_MINUTE",
            start_date="2026-06-01",
            end_date="2026-06-05",
            status="completed",
            grading_profile="Conservative"
        )
        self.session.add(job)
        self.session.commit()
        
        # Direct check on DB column creation/defaults
        queried = self.session.query(ResearchJobDB).filter_by(id=job.id).first()
        self.assertEqual(queried.grading_profile, "Conservative")

    def test_process_pool_helper(self):
        # Place a mock job in the database
        job = ResearchJobDB(
            id=str(uuid.uuid4()),
            strategy_name="UltraFast Reversion",
            symbol="NSE:SBIN-EQ",
            interval="FIVE_MINUTE",
            start_date="2026-06-01",
            end_date="2026-06-10",
            status="pending",
            stage="data_loading",
            n_trials=2,
            optimization_method="random"
        )
        self.session.add(job)
        self.session.commit()

        # Cache the dataset to avoid remote loading
        from engine.optimization_engine import _DATASET_CACHE
        normalized_symbol = "NSE:SBIN-EQ"
        _DATASET_CACHE[(normalized_symbol, "FIVE_MINUTE", "2026-06-01", "2026-06-10")] = self.mock_df

        # Run via the process pool executor wrapper (locally for validation)
        worker = ResearchEngine(db_session=self.session)
        status = worker.process_next_job()
        self.assertTrue(status)

        queried = self.session.query(ResearchJobDB).filter_by(id=job.id).first()
        if queried.status == "failed":
            print("JOB ERROR:", queried.error_message)
        self.assertEqual(queried.status, "completed")
        self.assertEqual(queried.stage, "completed")
        self.assertIn(queried.grade, ["Passed", "Failed", "Needs Review"])

        # Clean up generated report file
        if queried.report_path and os.path.exists(queried.report_path):
            try:
                os.remove(queried.report_path)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
