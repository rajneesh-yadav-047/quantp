"""
Monte Carlo Risk Analysis.

Provides:
- Monte Carlo simulation of trade P&L sequences
- Risk-of-ruin estimation
- Confidence intervals for expected returns
- Worst-case drawdown projections
- Stress testing under adverse market conditions
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Core Monte Carlo engine
# ---------------------------------------------------------------------------


def simulate_trade_sequences(
    trade_pnls: List[float],
    n_simulations: int = 1000,
    initial_capital: float = 100_000.0,
    seed: Optional[int] = 42,
) -> Dict[str, Any]:
    """
    Simulate `n_simulations` random orderings of historical trade P&L.

    For each simulation:
    - Shuffle the trade sequence
    - Compute cumulative equity curve

    Returns confidence intervals, risk-of-ruin, expected return distribution.
    """
    if not trade_pnls:
        return {"error": "No trade P&L data provided"}

    rng = np.random.default_rng(seed)
    pnls = np.array(trade_pnls, dtype=float)
    n_trades = len(pnls)

    final_equities: List[float] = []
    max_drawdowns: List[float] = []
    ruins: int = 0

    # Store a sample of equity curves for visualisation (max 20)
    sample_curves: List[List[float]] = []

    for sim_i in range(n_simulations):
        shuffled = rng.permutation(pnls)
        equity = np.cumsum(shuffled) + initial_capital

        # Drawdown
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        max_dd = float(np.max(dd))

        final_eq = float(equity[-1])
        final_equities.append(final_eq)
        max_drawdowns.append(max_dd)

        if final_eq <= 0:
            ruins += 1

        if sim_i < 20:
            sample_curves.append(equity.tolist())

    final_equities_arr = np.array(final_equities)
    max_drawdowns_arr = np.array(max_drawdowns)

    return {
        "n_simulations": n_simulations,
        "n_trades": n_trades,
        "initial_capital": initial_capital,
        # Final equity distribution
        "final_equity": {
            "mean": round(float(np.mean(final_equities_arr)), 2),
            "median": round(float(np.median(final_equities_arr)), 2),
            "p5": round(float(np.percentile(final_equities_arr, 5)), 2),
            "p25": round(float(np.percentile(final_equities_arr, 25)), 2),
            "p75": round(float(np.percentile(final_equities_arr, 75)), 2),
            "p95": round(float(np.percentile(final_equities_arr, 95)), 2),
            "std": round(float(np.std(final_equities_arr)), 2),
        },
        # Max drawdown distribution
        "max_drawdown": {
            "mean": round(float(np.mean(max_drawdowns_arr)), 4),
            "worst": round(float(np.max(max_drawdowns_arr)), 4),
            "p95": round(float(np.percentile(max_drawdowns_arr, 95)), 4),
            "p75": round(float(np.percentile(max_drawdowns_arr, 75)), 4),
        },
        # Risk metrics
        "risk_of_ruin_pct": round(ruins / n_simulations * 100, 2),
        "positive_outcome_pct": round(
            np.sum(final_equities_arr > initial_capital) / n_simulations * 100, 2
        ),
        # Confidence interval for expected return
        "expected_return_pct": {
            "mean": round((np.mean(final_equities_arr) - initial_capital) / initial_capital * 100, 2),
            "ci_95_low": round(
                (np.percentile(final_equities_arr, 2.5) - initial_capital) / initial_capital * 100, 2
            ),
            "ci_95_high": round(
                (np.percentile(final_equities_arr, 97.5) - initial_capital) / initial_capital * 100, 2
            ),
        },
        "sample_curves": sample_curves,
    }


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------


def stress_test(
    trade_pnls: List[float],
    initial_capital: float = 100_000.0,
    scenarios: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Apply adverse market stress scenarios by scaling all trade P&Ls.

    Default scenarios:
    - mild_bear   : P&L scaled by 0.7  (30% adverse)
    - moderate_bear: P&L scaled by 0.5  (50% adverse)
    - severe_bear : P&L scaled by 0.2  (80% adverse)
    - flash_crash  : Best 10% of trades zeroed out

    Returns metrics per scenario.
    """
    default_scenarios = {
        "mild_bear": 0.7,
        "moderate_bear": 0.5,
        "severe_bear": 0.2,
    }
    scenarios = scenarios or default_scenarios

    pnls = np.array(trade_pnls, dtype=float)
    results: Dict[str, Any] = {}

    for name, scale in scenarios.items():
        scaled = pnls * scale
        equity = np.cumsum(scaled) + initial_capital
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / np.where(peak > 0, peak, 1)
        final_eq = float(equity[-1])
        total_ret_pct = (final_eq - initial_capital) / initial_capital * 100
        results[name] = {
            "scale_factor": scale,
            "final_equity": round(final_eq, 2),
            "total_return_pct": round(total_ret_pct, 2),
            "max_drawdown": round(float(np.max(dd)), 4),
            "ruin": final_eq <= 0,
        }

    # Flash crash: zero out the 10% best trades
    if len(pnls) >= 10:
        flash = pnls.copy()
        top10_idx = np.argsort(flash)[-max(1, len(flash) // 10):]
        flash[top10_idx] = 0.0
        equity = np.cumsum(flash) + initial_capital
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / np.where(peak > 0, peak, 1)
        final_eq = float(equity[-1])
        results["flash_crash"] = {
            "description": "Top 10% winning trades zeroed",
            "final_equity": round(final_eq, 2),
            "total_return_pct": round((final_eq - initial_capital) / initial_capital * 100, 2),
            "max_drawdown": round(float(np.max(dd)), 4),
            "ruin": final_eq <= 0,
        }

    return results
