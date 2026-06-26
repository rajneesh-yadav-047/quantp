import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import pandas as pd
import numpy as np
import uuid
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, ResearchJobDB, WalkForwardFoldDB, OptimizationTrialDB
from engine.strategy_registry.base import StrategyRegistry, auto_discover_strategies
from engine.strategy_registry.market_analyzer import MarketAnalyzer
from engine.optimization_engine import OptimizationEngine, IndicatorCacheContext
from engine.robustness_engine import RobustnessEngine
from engine.research_engine import ResearchEngine, REPORTS_DIR


class TestFullResearchPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Make sure strategies are discovered
        auto_discover_strategies()

    def setUp(self):
        # Database setup in memory
        self.db_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=self.db_engine)
        self.session = Session()
        Base.metadata.create_all(bind=self.db_engine)

        # Generate mock market data (150 candles)
        np.random.seed(42)
        dates = pd.date_range(start="2026-06-01", periods=150, freq="5min")
        close_prices = np.random.randn(150).cumsum() + 100.0
        self.mock_df = pd.DataFrame({
            "time": dates.strftime('%Y-%m-%d %H:%M:%S'),
            "open": close_prices - 0.5,
            "high": close_prices + 1.0,
            "low": close_prices - 1.0,
            "close": close_prices,
            "volume": np.random.randint(100, 1000, size=150)
        })

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.db_engine)

    def test_1_strategy_registry(self):
        """1. Verify strategy registry auto-discovery and listing."""
        available = StrategyRegistry.list_strategies()
        self.assertGreater(len(available), 0, "Registry should contain discovered strategies.")
        
        # Verify VWAP Reversion or Bollinger Reversion is present
        self.assertTrue(any("Reversion" in s or "Following" in s for s in available))
        
        # Verify metadata loading
        klass = StrategyRegistry.get(available[0])
        self.assertIsNotNone(klass)
        self.assertIsNotNone(klass.metadata.name)
        self.assertIsNotNone(klass.parameter_specs)

    def test_2_market_analyzer(self):
        """2. Verify MarketAnalyzer compiles regimes and scores strategies."""
        symbol = "NSE:SBIN-EQ"
        analyzer = MarketAnalyzer(self.mock_df, symbol, "FIVE_MINUTE")
        profile = analyzer.analyze()
        
        self.assertIn("market_profile", profile)
        self.assertIn("strategy_rankings", profile)
        self.assertEqual(profile["market_profile"]["symbol"], symbol)
        
        # Verify regime classifications
        regime = profile["market_profile"]["regime"]["current_regime"]
        self.assertIn(regime, ["TRENDING_BULLISH", "TRENDING_BEARISH", "VOLATILE_RANGING", "QUIET_RANGING", "GAP_DAY", "UNKNOWN"])

    def test_3_optimization_engine_caching(self):
        """3. Verify OptimizationEngine technical indicator caching."""
        s = pd.Series(self.mock_df["close"])
        
        with IndicatorCacheContext() as cache_ctx:
            # Check ewm
            ewm1 = s.ewm(span=9).mean()
            ewm2 = s.ewm(span=9).mean()
            
            # Check rolling
            roll1 = s.rolling(window=15).mean()
            roll2 = s.rolling(window=15).mean()
            
            # Check rolling std
            std1 = s.rolling(window=15).std()
            std2 = s.rolling(window=15).std()
            
            self.assertGreater(len(cache_ctx.cache), 0)
            pd.testing.assert_series_equal(ewm1, ewm2)
            pd.testing.assert_series_equal(roll1, roll2)
            pd.testing.assert_series_equal(std1, std2)

    def test_4_optimization_runs(self):
        """4. Verify OptimizationEngine parameters tuning runs."""
        # Setup simple mock study
        opt_engine = OptimizationEngine(
            df_dict={"NSE:SBIN-EQ": self.mock_df},
            strategy_code="""
class Strategy:
    def on_bar(self, df, i):
        return []
""",
            initial_capital=100000.0,
            default_trade_type="INTRADAY"
        )
        
        param_grid = {
            "fast_period": [5, 10],
            "slow_period": [20, 30]
        }
        
        res = opt_engine.run_optimization(
            param_grid=param_grid,
            method="random",
            n_trials=3
        )
        
        self.assertEqual(res["total_runs"], 3)
        self.assertIn("best_parameters", res)

    def test_5_robustness_metrics_and_gpu(self):
        """5. Verify RobustnessEngine checks and CPU/GPU Monte Carlo simulations."""
        robust_engine = RobustnessEngine(initial_capital=100000.0)
        
        # Test sensitivity, degradation, distribution, drawdowns, consistency
        sensitivity = {"sensitivity_index": 0.2, "cv": 0.1, "stable": True}
        degradation = {"degradation_pct": 12.5}
        distribution = {"quality_grade": "ACCEPTABLE"}
        drawdowns = {"max_drawdown_pct": 14.5}
        consistency = {"negative_periods_pct": 8.0}
        
        # Run Monte Carlo
        trade_pnls = [100.0, -50.0, 120.0, -80.0, 150.0, 20.0, -40.0, 200.0]
        mc_report = robust_engine.run_monte_carlo(trade_pnls, n_simulations=50)
        
        self.assertIn("probability_of_ruin_pct", mc_report)
        self.assertIn("worst_case_drawdown_pct", mc_report)
        
        # Check overall score
        score = robust_engine.compute_robustness_score(
            sensitivity, degradation, distribution, drawdowns, consistency, mc_report
        )
        self.assertTrue(0.0 <= score <= 100.0)

    def test_6_research_engine_workflow(self):
        """6. Verify ResearchEngine workflow end-to-end with local DB session."""
        available_strats = StrategyRegistry.list_strategies()
        strategy_name = available_strats[0]

        # 1. Create a pending job
        job = ResearchJobDB(
            id=str(uuid.uuid4()),
            strategy_name=strategy_name,
            symbol="NSE:SBIN-EQ",
            interval="FIVE_MINUTE",
            start_date="2026-06-01",
            end_date="2026-06-15",
            status="pending",
            stage="data_loading",
            n_trials=5,
            optimization_method="random"
        )
        self.session.add(job)
        self.session.commit()

        # 2. Run background worker step
        worker = ResearchEngine(db_session=self.session)
        
        # Override data loading logic for testing by putting mock data into cache
        from engine.optimization_engine import _DATASET_CACHE
        normalized_symbol = "NSE:SBIN-EQ"
        _DATASET_CACHE[(normalized_symbol, "FIVE_MINUTE", "2026-06-01", "2026-06-15")] = self.mock_df

        # Execute
        run_status = worker.process_next_job()
        self.assertTrue(run_status, "Worker should successfully run the pending job.")
        
        # Check job completion and report files
        queried = self.session.query(ResearchJobDB).filter_by(id=job.id).first()
        self.assertEqual(queried.status, "completed")
        self.assertEqual(queried.stage, "completed")
        self.assertEqual(queried.progress, 100.0)
        self.assertIn(queried.grade, ["Passed", "Failed", "Needs Review"])
        self.assertTrue(os.path.exists(queried.report_path))
        
        # Clean up generated report file
        if queried.report_path and os.path.exists(queried.report_path):
            os.remove(queried.report_path)


if __name__ == "__main__":
    unittest.main()
