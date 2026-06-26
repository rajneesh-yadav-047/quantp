import os
import unittest
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, ResearchJobDB, WalkForwardFoldDB, OptimizationTrialDB
from engine.optimization_engine import IndicatorCacheContext, OptimizationEngine
from engine.robustness_engine import RobustnessEngine
from engine.research_engine import ResearchEngine


class TestResearchPlatform(unittest.TestCase):
    def setUp(self):
        # In-memory database setup for tests
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(bind=self.engine)

        # Create dummy market data
        dates = pd.date_range(start="2026-06-01", periods=100, freq="5min")
        self.dummy_df = pd.DataFrame({
            "time": dates.strftime('%Y-%m-%d %H:%M:%S'),
            "open": np.random.randn(100).cumsum() + 100.0,
            "high": np.random.randn(100).cumsum() + 101.0,
            "low": np.random.randn(100).cumsum() + 99.0,
            "close": np.random.randn(100).cumsum() + 100.0,
            "volume": np.random.randint(100, 1000, size=100)
        })

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_database_models(self):
        """Verifies that research platform database models serialize and deserialize correctly."""
        # 1. Job
        job = ResearchJobDB(
            id="test-job-id",
            strategy_name="Trend Following",
            symbol="NSE:SBIN-EQ",
            interval="FIVE_MINUTE",
            start_date="2026-06-01",
            end_date="2026-06-02",
            status="pending",
            stage="data_loading",
            progress=0.0
        )
        self.session.add(job)
        self.session.commit()

        queried_job = self.session.query(ResearchJobDB).filter_by(id="test-job-id").first()
        self.assertIsNotNone(queried_job)
        self.assertEqual(queried_job.strategy_name, "Trend Following")

        # 2. Fold
        fold = WalkForwardFoldDB(
            job_id="test-job-id",
            fold_index=0,
            train_start="2026-06-01",
            train_end="2026-06-02",
            val_start="2026-06-02",
            val_end="2026-06-03",
            test_start="2026-06-03",
            test_end="2026-06-04",
            status="pending"
        )
        self.session.add(fold)
        self.session.commit()

        queried_fold = self.session.query(WalkForwardFoldDB).filter_by(job_id="test-job-id").first()
        self.assertIsNotNone(queried_fold)
        self.assertEqual(queried_fold.fold_index, 0)

    def test_indicator_caching(self):
        """Verifies that the indicator cache context wrapper caches rolling calculations."""
        s = pd.Series(np.random.randn(1000))
        
        with IndicatorCacheContext() as cache_ctx:
            # First computation
            res1 = s.ewm(span=10).mean()
            # Second computation (should hit cache)
            res2 = s.ewm(span=10).mean()

            # First rolling standard deviation
            std1 = s.rolling(window=20).std()
            # Second rolling standard deviation (should hit cache)
            std2 = s.rolling(window=20).std()
            
            # The cache should be populated
            self.assertGreater(len(cache_ctx.cache), 0)
            
            # Assert equality
            pd.testing.assert_series_equal(res1, res2)
            pd.testing.assert_series_equal(std1, std2)

    def test_robustness_metrics(self):
        """Verifies robustness scoring and Monte Carlo CPU/GPU execution."""
        trades = [150.0, -100.0, 200.0, -50.0, 300.0, -120.0, 400.0]
        equity_curve = [100000.0, 100150.0, 100050.0, 100250.0, 100200.0, 100500.0, 100380.0, 100780.0]

        robust_engine = RobustnessEngine(initial_capital=100000.0)
        
        # Test sensitivity calculation
        sensitivity = robust_engine.analyze_parameter_sensitivity(
            sweep_results=[{"score": 1.5, "status": "SUCCESS"}, {"score": 1.2, "status": "SUCCESS"}],
            best_params={}
        )
        self.assertIn("sensitivity_index", sensitivity)

        # Test degradation check
        degradation = robust_engine.analyze_degradation(1.5, 1.2, 1.1)
        self.assertEqual(degradation["overfit_risk"], "LOW")

        # Test trade distribution checks
        dist = robust_engine.analyze_trade_distribution(trades)
        self.assertEqual(dist["quality_grade"], "ACCEPTABLE")

        # Test Monte Carlo simulations
        mc = robust_engine.run_monte_carlo(trades, n_simulations=100)
        self.assertLess(mc["probability_of_ruin_pct"], 10.0)
        self.assertGreater(mc["median_final_equity"], 100000.0)

    def test_auto_grading(self):
        """Verifies correct strategy auto-grading thresholds (Passed, Failed, Needs Review)."""
        robust_engine = RobustnessEngine(initial_capital=100000.0)
        
        # Criteria definitions
        sensitivity = {"sensitivity_index": 0.2}
        degradation = {"degradation_pct": 10.0}
        distribution = {"quality_grade": "EXCELLENT"}
        drawdowns = {"max_drawdown_pct": 15.0}
        consistency = {"negative_periods_pct": 5.0}
        monte_carlo = {"probability_of_ruin_pct": 0.0, "worst_case_drawdown_pct": 20.0}

        score = robust_engine.compute_robustness_score(
            sensitivity, degradation, distribution, drawdowns, consistency, monte_carlo
        )
        self.assertGreaterEqual(score, 60.0)


if __name__ == "__main__":
    unittest.main()
