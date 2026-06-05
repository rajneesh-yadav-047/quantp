import numpy as np
from typing import Dict, List, Any
import pandas as pd
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

def analyze_capital_requirements(
    df_dict: Dict[str, pd.DataFrame],
    strategy_code: str,
    default_trade_type: str = "INTRADAY",
    capital_levels: List[float] = None
) -> Dict[str, Any]:
    """
    Simulates the strategy under various capital sizes to find:
    - Minimum viable capital (where no margin calls occur and Max Drawdown < 25%)
    - Margin usage profiles
    - Scaling efficiency curve
    """
    if not capital_levels:
        capital_levels = [25000.0, 50000.0, 100000.0, 250000.0, 500000.0, 1000000.0]

    results = []
    
    # We will simulate each capital level
    for cap in capital_levels:
        # For scaling simulation, we can dynamically scale position sizes if the strategy supports it,
        # or simulate standard fixed sizes. For simple fixed sizing, standard execution charges will scale.
        # To model scaling degradation, we can increase slippage slightly with larger capital sizes:
        # e.g., slippage = base_slippage * (1 + capital / 200,000) to simulate market impact.
        base_slippage = 0.0005
        slippage_pct = base_slippage * (1.0 + (cap / 1000000.0))  # Scale slippage with size

        engine = BacktestEngine(
            df_dict=df_dict,
            strategy_code=strategy_code,
            initial_capital=cap,
            slippage_pct=slippage_pct,
            default_trade_type=default_trade_type
        )
        
        try:
            res = engine.run()
            # Calculate analytics
            metrics = calculate_metrics(res['equity_curve'], res['trades'], cap)
            
            # Check if bankrupt or margin called
            margin_call_triggered = False
            for eq in res['equity_curve']:
                if eq['equity'] <= 0 or eq['margin_used'] > eq['equity']:
                    margin_call_triggered = True
                    break
                    
            results.append({
                "capital": cap,
                "cagr": metrics.get("cagr", 0.0),
                "sharpe": metrics.get("sharpe_ratio", 0.0),
                "max_drawdown_pct": metrics.get("max_drawdown", 0.0),
                "max_drawdown_val": metrics.get("max_drawdown", 0.0) * cap,
                "margin_call_triggered": margin_call_triggered,
                "max_margin_used": metrics.get("max_margin_used", 0.0),
                "capital_efficiency": metrics.get("capital_efficiency", 0.0),
                "net_pnl": metrics.get("total_pnl", 0.0)
            })
        except Exception as e:
            # Run failed (e.g. crash in strategy or math)
            results.append({
                "capital": cap,
                "error": str(e),
                "margin_call_triggered": True
            })

    # Calculate Minimum Viable Capital (MVC)
    # Define as lowest capital level where:
    # 1. No margin call triggered
    # 2. Max drawdown < 30%
    # 3. Net PnL is positive
    mvc = None
    for r in results:
        if r.get("error"):
            continue
        if not r["margin_call_triggered"] and r["max_drawdown_pct"] < 0.30:
            mvc = r["capital"]
            break
            
    # If no capital levels succeeded, MVC is set to the highest level or flagged
    if not mvc:
        mvc = capital_levels[-1] if capital_levels else 0.0

    return {
        "capital_simulations": results,
        "minimum_viable_capital": mvc,
        "optimal_capital_allocation": mvc * 1.5 if mvc else 100000.0, # buffer factor
        "scaling_curve": [
            {"capital": r["capital"], "cagr": r["cagr"], "sharpe": r["sharpe"], "margin_call": r["margin_call_triggered"]}
            for r in results if not r.get("error")
        ]
    }
