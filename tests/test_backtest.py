import os
import sys
import pandas as pd

# Ensure workspace folders are in system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.datamodels import MarketState, OrderRequest
from engine.execution import ExecutionSimulator
from engine.runtime import SandboxedStrategyRuntime
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

def test_fee_calculator():
    sim = ExecutionSimulator()
    # Test intraday buy charges on 10 shares of RELIANCE at 2500
    brokerage, stt, exc, gst, sebi, stamp, total = sim.calculate_charges(
        symbol="RELIANCE",
        direction="BUY",
        price=2500.0,
        qty=10,
        trade_type="INTRADAY"
    )
    
    assert brokerage <= 20.0
    assert stamp > 0.0
    assert gst > 0.0
    assert total > 0.0
    
    # Sell side has STT, Buy side does not for intraday
    _, sell_stt, _, _, _, _, _ = sim.calculate_charges(
        symbol="RELIANCE",
        direction="SELL",
        price=2500.0,
        qty=10,
        trade_type="INTRADAY"
    )
    assert sell_stt > 0.0

def test_sandbox_safety():
    # Attempting to import forbidden libraries
    unsafe_code = """
class Strategy:
    def on_bar(self, state):
        import os
        os.system("echo 'hack'")
        return []
"""
    runtime = SandboxedStrategyRuntime(unsafe_code)
    
    # Construct dummy state
    from engine.datamodels import Portfolio
    dummy_portfolio = Portfolio(cash=10000.0)
    dummy_state = MarketState(
        current_time="2026-06-01 09:15:00",
        current_candle={},
        historical_candles={},
        positions={},
        portfolio=dummy_portfolio,
        active_orders=[]
    )
    
    runtime.on_bar(dummy_state)
    logs = runtime.get_logs()
    
    error_logged = any("Import of module 'os' is restricted" in log for log in logs)
    assert error_logged, f"Sandboxed runtime failed to block unauthorized imports! Logs: {logs}"

def test_backtester_runs():
    # Generate some simple mock prices
    prices = [500.0, 502.0, 498.0, 505.0, 510.0, 508.0, 512.0, 515.0, 520.0, 518.0, 522.0, 525.0]
    dates = [f"2026-06-01 09:{15+i:02d}:00" for i in range(len(prices))]
    
    df = pd.DataFrame({
        "time": dates,
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [1000] * len(prices)
    })
    
    strategy_code = """
class Strategy:
    def on_bar(self, state):
        # Buy on first bar, sell on 5th bar
        orders = []
        hist = state.historical_candles.get("SBIN", [])
        if len(hist) == 1:
            orders.append({"symbol": "SBIN", "direction": "BUY", "type": "MARKET", "price": 0.0, "qty": 10})
        elif len(hist) == 5:
            orders.append({"symbol": "SBIN", "direction": "SELL", "type": "MARKET", "price": 0.0, "qty": 10})
        return orders
"""
    
    engine = BacktestEngine(
        df_dict={"SBIN": df},
        strategy_code=strategy_code,
        initial_capital=10000.0,
        log_dir="./test_logs"
    )
    
    res = engine.run()
    assert res['run_id'] is not None
    assert len(res['trades']) == 2
    assert res['final_portfolio']['equity'] is not None
    
    # Clean up logs
    if os.path.exists(res['log_file_path']):
        os.remove(res['log_file_path'])
    if os.path.exists("./test_logs"):
        try:
            os.rmdir("./test_logs")
        except OSError:
            pass

if __name__ == "__main__":
    test_fee_calculator()
    test_sandbox_safety()
    test_backtester_runs()
    print("All tests passed successfully!")
