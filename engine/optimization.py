import itertools
from typing import Dict, List, Any, Tuple
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

def run_parameter_sweep(
    df_dict: Dict[str, pd.DataFrame],
    strategy_code: str,
    param_grid: Dict[str, List[Any]],
    initial_capital: float = 100000.0,
    default_trade_type: str = "INTRADAY",
    max_workers: int = 4
) -> Dict[str, Any]:
    """
    Runs a parameter sweep grid search on the strategy.
    param_grid format: {"ema_fast": [5, 9, 15], "ema_slow": [20, 30, 50]}
    """
    # Generate all combinations of parameter values
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    sweep_results = []

    def evaluate_combination(params: Dict[str, Any]) -> Dict[str, Any]:
        engine = BacktestEngine(
            df_dict=df_dict,
            strategy_code=strategy_code,
            initial_capital=initial_capital,
            default_trade_type=default_trade_type,
            parameters=params
        )
        try:
            res = engine.run()
            metrics = calculate_metrics(res['equity_curve'], res['trades'], initial_capital)
            
            return {
                "parameters": params,
                "cagr": metrics.get("cagr", 0.0),
                "sharpe": metrics.get("sharpe_ratio", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "win_rate": metrics.get("win_rate", 0.0),
                "total_trades": metrics.get("trade_metrics", {}).get("total_trades", 0),
                "total_pnl": metrics.get("total_pnl", 0.0),
                "status": "SUCCESS"
            }
        except Exception as e:
            return {
                "parameters": params,
                "status": "FAILED",
                "error": str(e)
            }

    # Execute in parallel
    if len(combinations) > 1 and max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            sweep_results = list(executor.map(evaluate_combination, combinations))
    else:
        # Sequential fallback
        for combo in combinations:
            sweep_results.append(evaluate_combination(combo))

    # Identify the best combination based on Sharpe Ratio
    best_combo = None
    best_sharpe = -999.0
    for r in sweep_results:
        if r["status"] == "SUCCESS" and r["sharpe"] > best_sharpe:
            best_sharpe = r["sharpe"]
            best_combo = r

    return {
        "results": sweep_results,
        "best_result": best_combo,
        "parameter_names": list(keys),
        "total_runs": len(combinations)
    }
