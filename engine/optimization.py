"""
Optimizer & Hyper-parameter Search.

Extends the existing grid search with:
- Random search
- Sensitivity analysis (per-parameter impact)
- Sharpe and Drawdown heatmaps (2D)
- Automated overfitting detection (train vs. test comparison)
- Parameter ranking by importance
"""

from __future__ import annotations

import itertools
import random
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evaluate_combination(
    df_dict: Dict[str, pd.DataFrame],
    strategy_code: str,
    params: Dict[str, Any],
    initial_capital: float,
    default_trade_type: str,
) -> Dict[str, Any]:
    try:
        engine = BacktestEngine(
            df_dict=df_dict,
            strategy_code=strategy_code,
            initial_capital=initial_capital,
            default_trade_type=default_trade_type,
            parameters=params,
        )
        res = engine.run()
        metrics = calculate_metrics(res["equity_curve"], res["trades"], initial_capital)
        return {
            "parameters": params,
            "cagr": metrics.get("cagr", 0.0),
            "sharpe": metrics.get("sharpe_ratio", 0.0),
            "sortino": metrics.get("sortino_ratio", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "win_rate": metrics.get("win_rate", 0.0),
            "total_trades": metrics.get("trade_metrics", {}).get("total_trades", 0),
            "total_pnl": metrics.get("total_pnl", 0.0),
            "status": "SUCCESS",
        }
    except Exception as e:
        return {"parameters": params, "status": "FAILED", "error": str(e)}


# ---------------------------------------------------------------------------
# Grid search (enhanced from existing)
# ---------------------------------------------------------------------------


def run_parameter_sweep(
    df_dict: Dict[str, pd.DataFrame],
    strategy_code: str,
    param_grid: Dict[str, List[Any]],
    initial_capital: float = 100_000.0,
    default_trade_type: str = "INTRADAY",
    max_workers: int = 4,
) -> Dict[str, Any]:
    """
    Grid search over all parameter combinations.
    Backward-compatible with existing /api/research/optimize endpoint.
    """
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    def _eval(p):
        return _evaluate_combination(df_dict, strategy_code, p, initial_capital, default_trade_type)

    if len(combinations) > 1 and max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            sweep_results = list(ex.map(_eval, combinations))
    else:
        sweep_results = [_eval(p) for p in combinations]

    best_combo = None
    best_sharpe = -999.0
    for r in sweep_results:
        if r["status"] == "SUCCESS" and r["sharpe"] > best_sharpe:
            best_sharpe = r["sharpe"]
            best_combo = r

    return {
        "results": sweep_results,
        "best_result": best_combo,
        "parameter_names": keys,
        "total_runs": len(combinations),
        "search_type": "grid",
    }


# ---------------------------------------------------------------------------
# Random search
# ---------------------------------------------------------------------------


def run_random_search(
    df_dict: Dict[str, pd.DataFrame],
    strategy_code: str,
    param_grid: Dict[str, List[Any]],
    n_trials: int = 30,
    initial_capital: float = 100_000.0,
    default_trade_type: str = "INTRADAY",
    max_workers: int = 4,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Random search: sample `n_trials` random parameter combinations.
    Much faster than grid search for large parameter spaces.
    """
    rng = random.Random(seed)
    combinations = [
        {k: rng.choice(v) for k, v in param_grid.items()}
        for _ in range(n_trials)
    ]

    def _eval(p):
        return _evaluate_combination(df_dict, strategy_code, p, initial_capital, default_trade_type)

    if n_trials > 1 and max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            sweep_results = list(ex.map(_eval, combinations))
    else:
        sweep_results = [_eval(p) for p in combinations]

    successes = [r for r in sweep_results if r["status"] == "SUCCESS"]
    best_combo = max(successes, key=lambda r: r["sharpe"]) if successes else None

    return {
        "results": sweep_results,
        "best_result": best_combo,
        "parameter_names": list(param_grid.keys()),
        "total_runs": n_trials,
        "search_type": "random",
    }


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------


def sensitivity_analysis(
    sweep_results: List[Dict[str, Any]],
    metric: str = "sharpe",
) -> Dict[str, Any]:
    """
    Compute per-parameter sensitivity: how much does `metric` vary
    when each parameter changes, holding others fixed?

    Returns a ranking of parameters by impact (std of metric across values).
    """
    successes = [r for r in sweep_results if r.get("status") == "SUCCESS"]
    if not successes:
        return {"error": "No successful runs"}

    all_params = list(successes[0]["parameters"].keys())
    sensitivity: Dict[str, float] = {}

    for param in all_params:
        param_values = {}
        for r in successes:
            pval = r["parameters"].get(param)
            if pval not in param_values:
                param_values[pval] = []
            param_values[pval].append(r.get(metric, 0.0))

        # Std of mean-metric across parameter values
        means = [np.mean(v) for v in param_values.values()]
        sensitivity[param] = float(np.std(means)) if len(means) > 1 else 0.0

    ranked = sorted(sensitivity.items(), key=lambda x: x[1], reverse=True)

    return {
        "sensitivity": sensitivity,
        "ranked_parameters": [{"parameter": k, "impact": round(v, 4)} for k, v in ranked],
        "most_important": ranked[0][0] if ranked else None,
    }


# ---------------------------------------------------------------------------
# 2D heatmap data (for Sharpe / Drawdown)
# ---------------------------------------------------------------------------


def build_heatmap(
    sweep_results: List[Dict[str, Any]],
    param_x: str,
    param_y: str,
    metric: str = "sharpe",
) -> Dict[str, Any]:
    """
    Build a 2D heatmap of `metric` for two parameters.

    Returns x_values, y_values, and a 2D matrix.
    """
    successes = [r for r in sweep_results if r.get("status") == "SUCCESS"]
    if not successes:
        return {"error": "No successful runs"}

    x_vals = sorted(set(r["parameters"].get(param_x) for r in successes))
    y_vals = sorted(set(r["parameters"].get(param_y) for r in successes))

    matrix = [[None for _ in x_vals] for _ in y_vals]

    for r in successes:
        px = r["parameters"].get(param_x)
        py = r["parameters"].get(param_y)
        val = r.get(metric, 0.0)
        if px in x_vals and py in y_vals:
            xi = x_vals.index(px)
            yi = y_vals.index(py)
            if matrix[yi][xi] is None or val > matrix[yi][xi]:
                matrix[yi][xi] = val

    # Fill None with 0
    matrix = [[v if v is not None else 0.0 for v in row] for row in matrix]

    return {
        "param_x": param_x,
        "param_y": param_y,
        "metric": metric,
        "x_values": x_vals,
        "y_values": y_vals,
        "matrix": matrix,
    }


# ---------------------------------------------------------------------------
# Overfitting detection (train vs test)
# ---------------------------------------------------------------------------


def detect_overfitting(
    train_results: List[Dict[str, Any]],
    test_results: List[Dict[str, Any]],
    metric: str = "sharpe",
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Compare train vs. test performance to detect overfitting.

    Correlation between train and test performance for each parameter combo
    is a key indicator: low correlation = high overfitting risk.
    """
    train_ok = {
        str(r["parameters"]): r.get(metric, 0.0)
        for r in train_results
        if r.get("status") == "SUCCESS"
    }
    test_ok = {
        str(r["parameters"]): r.get(metric, 0.0)
        for r in test_results
        if r.get("status") == "SUCCESS"
    }

    common_keys = list(set(train_ok) & set(test_ok))
    if len(common_keys) < 2:
        return {"error": "Not enough common runs to compare"}

    train_vals = np.array([train_ok[k] for k in common_keys])
    test_vals = np.array([test_ok[k] for k in common_keys])

    corr = float(np.corrcoef(train_vals, test_vals)[0, 1]) if len(common_keys) > 1 else 0.0
    train_mean = float(np.mean(train_vals))
    test_mean = float(np.mean(test_vals))
    degradation = (train_mean - test_mean) / abs(train_mean) if train_mean != 0 else 0.0

    overfit_risk = "LOW" if corr > 0.7 and degradation < 0.3 else (
        "MEDIUM" if corr > 0.4 else "HIGH"
    )

    return {
        "n_common_runs": len(common_keys),
        "train_mean": round(train_mean, 4),
        "test_mean": round(test_mean, 4),
        "degradation_pct": round(degradation * 100, 2),
        "correlation": round(corr, 4),
        "overfit_risk": overfit_risk,
        "verdict": "OVERFIT" if overfit_risk == "HIGH" else "ACCEPTABLE",
    }
