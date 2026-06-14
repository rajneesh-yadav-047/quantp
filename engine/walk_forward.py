"""
Walk-Forward Testing & Robustness Pipeline.

Components:
- WalkForwardTester  : rolling window train/validation/test splits
- RobustnessAnalyzer : overfitting detection, parameter stability, robustness score
"""

from __future__ import annotations

import itertools
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Walk-forward tester
# ---------------------------------------------------------------------------


class WalkForwardTester:
    """
    Executes walk-forward backtesting with rolling windows.

    Parameters
    ----------
    df_dict : symbol -> DataFrame (full history)
    strategy_fn : callable(df_dict_slice, params) -> dict with 'equity_curve', 'trades'
    """

    def __init__(
        self,
        df_dict: Dict[str, pd.DataFrame],
        strategy_fn: Callable,
        train_size: int = 200,
        val_size: int = 50,
        test_size: int = 50,
        step_size: int = 50,
        time_col: str = "time",
    ):
        self.df_dict = df_dict
        self.strategy_fn = strategy_fn
        self.train_size = train_size
        self.val_size = val_size
        self.test_size = test_size
        self.step_size = step_size
        self.time_col = time_col

    def _all_timestamps(self) -> List[str]:
        """Collect and sort all unique timestamps across all symbols."""
        ts: set = set()
        for df in self.df_dict.values():
            if self.time_col in df.columns:
                ts.update(df[self.time_col].astype(str).tolist())
        return sorted(ts)

    def _slice_at(
        self,
        timestamps: List[str],
        start_idx: int,
        end_idx: int,
    ) -> Dict[str, pd.DataFrame]:
        """Return df_dict sliced to timestamp indices [start_idx, end_idx)."""
        window_ts = set(timestamps[start_idx:end_idx])
        result: Dict[str, pd.DataFrame] = {}
        for sym, df in self.df_dict.items():
            mask = df[self.time_col].astype(str).isin(window_ts)
            result[sym] = df[mask].copy().reset_index(drop=True)
        return result

    def run(
        self,
        params: Dict[str, Any],
        metrics_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute walk-forward test.

        Parameters
        ----------
        params : strategy parameters dict
        metrics_fn : callable(equity_curve, trades, capital) -> dict
                     If None, uses basic equity-curve metrics.

        Returns
        -------
        dict with 'windows' list and 'summary' aggregate stats
        """
        timestamps = self._all_timestamps()
        total = len(timestamps)
        window_results: List[Dict[str, Any]] = []
        window_size = self.train_size + self.val_size + self.test_size
        idx = 0

        while idx + window_size <= total:
            train_end = idx + self.train_size
            val_end = train_end + self.val_size
            test_end = val_end + self.test_size

            train_data = self._slice_at(timestamps, idx, train_end)
            val_data = self._slice_at(timestamps, train_end, val_end)
            test_data = self._slice_at(timestamps, val_end, test_end)

            try:
                train_res = self.strategy_fn(train_data, params)
                val_res = self.strategy_fn(val_data, params)
                test_res = self.strategy_fn(test_data, params)

                def _basic_metrics(res: Dict) -> Dict[str, float]:
                    eq = res.get("equity_curve", [])
                    if not eq:
                        return {"total_return": 0.0, "sharpe": 0.0, "max_dd": 0.0}
                    equities = [e["equity"] for e in eq]
                    rets = np.diff(equities) / np.array(equities[:-1])
                    peak = np.maximum.accumulate(equities)
                    dd = (peak - equities) / peak
                    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0
                    mu, sigma = float(np.mean(rets)), float(np.std(rets))
                    sharpe = (mu / sigma * np.sqrt(252)) if sigma > 0 else 0.0
                    total_ret = (equities[-1] - equities[0]) / equities[0] if equities[0] > 0 else 0.0
                    return {
                        "total_return": round(total_ret, 4),
                        "sharpe": round(sharpe, 4),
                        "max_dd": round(max_dd, 4),
                    }

                mfn = metrics_fn if metrics_fn else lambda r: _basic_metrics(r)

                window_results.append(
                    {
                        "window_start": timestamps[idx],
                        "train_end": timestamps[train_end - 1],
                        "val_end": timestamps[val_end - 1],
                        "test_end": timestamps[test_end - 1],
                        "train_metrics": mfn(train_res),
                        "val_metrics": mfn(val_res),
                        "test_metrics": mfn(test_res),
                    }
                )
            except Exception as e:
                window_results.append(
                    {
                        "window_start": timestamps[idx],
                        "error": str(e),
                    }
                )

            idx += self.step_size

        # Aggregate
        valid = [w for w in window_results if "error" not in w]
        summary: Dict[str, Any] = {}
        for split in ("train", "val", "test"):
            key = f"{split}_metrics"
            for metric in ("total_return", "sharpe", "max_dd"):
                vals = [w[key].get(metric, 0.0) for w in valid if key in w]
                summary[f"{split}_{metric}_mean"] = round(float(np.mean(vals)), 4) if vals else 0.0
                summary[f"{split}_{metric}_std"] = round(float(np.std(vals)), 4) if vals else 0.0

        return {"windows": window_results, "summary": summary}


# ---------------------------------------------------------------------------
# Robustness Analyzer
# ---------------------------------------------------------------------------


class RobustnessAnalyzer:
    """
    Analyze strategy robustness through overfitting detection and parameter stability.
    """

    @staticmethod
    def overfitting_score(
        train_sharpe: float,
        val_sharpe: float,
        test_sharpe: float,
    ) -> Dict[str, Any]:
        """
        Compute an overfitting score.

        Score = 0 (no overfit) to 100 (severe overfit).
        Based on relative degradation from train to out-of-sample.
        """
        oos_avg = (val_sharpe + test_sharpe) / 2
        if train_sharpe == 0:
            degradation = 0.0
        else:
            degradation = max(0.0, (train_sharpe - oos_avg) / abs(train_sharpe))

        overfit_score = min(100.0, degradation * 100)
        is_robust = overfit_score < 30

        return {
            "train_sharpe": round(train_sharpe, 4),
            "val_sharpe": round(val_sharpe, 4),
            "test_sharpe": round(test_sharpe, 4),
            "oos_avg_sharpe": round(oos_avg, 4),
            "degradation_pct": round(degradation * 100, 2),
            "overfit_score": round(overfit_score, 2),
            "is_robust": is_robust,
            "verdict": "ROBUST" if is_robust else "OVERFIT",
        }

    @staticmethod
    def parameter_stability(
        sweep_results: List[Dict[str, Any]],
        metric: str = "sharpe",
    ) -> Dict[str, Any]:
        """
        Assess how stable strategy performance is across parameter variations.

        sweep_results: list of dicts with 'parameters' and metric values.
        A stable strategy has low variance in performance across parameters.
        """
        scores = [r.get(metric, 0.0) for r in sweep_results if r.get("status") == "SUCCESS"]
        if not scores:
            return {"stable": False, "variance": 0.0, "cv": 0.0}

        mu = float(np.mean(scores))
        sigma = float(np.std(scores))
        cv = sigma / abs(mu) if mu != 0 else float("inf")

        return {
            "mean_score": round(mu, 4),
            "std_score": round(sigma, 4),
            "cv": round(cv, 4),
            "stable": cv < 0.5,
            "best_score": round(max(scores), 4),
            "worst_score": round(min(scores), 4),
        }

    @staticmethod
    def robustness_score(
        overfit_analysis: Dict[str, Any],
        stability_analysis: Dict[str, Any],
    ) -> float:
        """
        Combine overfitting and stability analyses into a single 0-100 score.
        Higher = more robust.
        """
        overfit_penalty = overfit_analysis.get("overfit_score", 50.0)
        stability_bonus = 0.0 if not stability_analysis.get("stable", False) else 20.0
        cv_penalty = min(30.0, stability_analysis.get("cv", 1.0) * 30)

        score = 100.0 - overfit_penalty - cv_penalty + stability_bonus
        return round(max(0.0, min(100.0, score)), 2)
