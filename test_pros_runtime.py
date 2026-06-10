import json
import sys
sys.path.insert(0, 'C:/Users/rajy7/quantp')

from engine.runtime.runtimes import ProsperityRuntime, RuntimeFactory
from engine.runtime.datamodels import TradingState, OrderDepth, Position

# Strategy code (the user's market order version)
strategy_code = '''
import json

class Trader:
    def run(self, state):
        result = {}
        for symbol, order_depth in state.order_depths.items():
            current_pos = state.position.get(symbol, 0)
            print(f"Tick | Symbol: {symbol} | Pos: {current_pos}")
            
            if current_pos == 0:
                result[symbol] = [{
                    "symbol": symbol,
                    "direction": "BUY",
                    "price": 0,
                    "quantity": 10,
                    "type": "MARKET"
                }]
                print(f"  -> MARKET BUY 10 units")
            elif current_pos >= 10:
                result[symbol] = [{
                    "symbol": symbol,
                    "direction": "SELL",
                    "price": 0,
                    "quantity": 10,
                    "type": "MARKET"
                }]
                print(f"  -> MARKET SELL 10 units")
            else:
                result[symbol] = []

        return result, 0, json.dumps({"pos": current_pos})
'''

# Create runtime
runtime = RuntimeFactory.create_runtime(strategy_code, runtime_type="prosperity_trader")
print(f"Runtime type: {type(runtime).__name__}")

# Build a fake TradingState
state = TradingState(
    timestamp="2026-06-01 09:15:00",
    order_depths={
        "SBIN": OrderDepth(
            symbol="SBIN",
            bid_prices=[499, 498],
            bid_volumes=[100, 200],
            ask_prices=[501, 502],
            ask_volumes=[50, 60]
        )
    },
    own_trades={"SBIN": []},
    market_trades={"SBIN": []},
    positions={"SBIN": Position(symbol="SBIN", quantity=0)},
    portfolio_value=100000,
    cash=100000,
    trader_data="{}"
)

# Run the strategy
orders, trader_data = runtime.on_tick(state)
print(f"\n=== ORDERS RETURNED ===")
print(f"Count: {len(orders)}")
for o in orders:
    print(f"  Order: {o}")

print(f"\n=== LOGS ===")
print(runtime.get_logs())
