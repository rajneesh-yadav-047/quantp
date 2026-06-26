import sys
import os
import unittest
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.strategy_registry.base import BaseStrategy, ParameterSpec, StrategyMetadata, StrategyRegistry

# Define a mock strategy for testing
class MockStrategyForRegistryTest(BaseStrategy):
    metadata = StrategyMetadata(
        name="Mock Registry Test Strategy",
        description="Used to verify StrategyRegistry enhancements.",
        regime_compatibility={"QUIET_RANGING": 100},
        preferred_timeframes=["FIVE_MINUTE"],
        typical_holding_bars=5,
        requires_volume=False,
    )
    
    parameter_specs = [
        ParameterSpec("period", "range_int", 20, 10, 50, step=1, description="Mock period"),
        ParameterSpec("threshold", "range_float", 2.0, 1.0, 5.0, step=0.1, description="Mock threshold"),
        ParameterSpec("mode", "choice", "fast", choices=["fast", "slow"], description="Mock mode"),
        ParameterSpec("enable_feature", "bool", True, description="Mock feature toggle")
    ]

    def entry_rules(self, market_state):
        return True

    def exit_rules(self, market_state, position):
        return True

    def stop_loss(self, entry_price, current_price, direction):
        return False

    def take_profit(self, entry_price, current_price, direction):
        return False

    def position_size(self, capital, atr, price):
        return 1

    def get_param_grid(self, granularity="medium"):
        return {"period": [20]}

    def generate_code(self, symbol):
        return "class Strategy: pass"


class TestStrategyRegistryEnhancements(unittest.TestCase):
    def setUp(self):
        # Register the mock strategy class manually
        StrategyRegistry.register(MockStrategyForRegistryTest)

    def tearDown(self):
        # Clear/cleanup if needed or just let it remain
        pass

    def test_parameter_validation_success(self):
        # Valid parameters should return no errors
        errors = MockStrategyForRegistryTest.validate_parameters({
            "period": 25,
            "threshold": 3.5,
            "mode": "slow",
            "enable_feature": False
        })
        self.assertEqual(len(errors), 0, f"Expected no errors, got: {errors}")

    def test_parameter_validation_out_of_bounds(self):
        # Invalid parameters should return clean descriptive error messages
        errors = MockStrategyForRegistryTest.validate_parameters({
            "period": 5,          # below min 10
            "threshold": 6.0,     # above max 5.0
            "mode": "invalid_mode", # not in choices
            "enable_feature": 123 # not a valid bool
        })
        
        self.assertEqual(len(errors), 4)
        self.assertTrue(any("below minimum" in e for e in errors))
        self.assertTrue(any("above maximum" in e for e in errors))
        self.assertTrue(any("not in choices" in e for e in errors))
        self.assertTrue(any("must be a boolean" in e for e in errors))

    def test_json_schema_generation(self):
        schema = MockStrategyForRegistryTest.get_parameter_schema()
        
        self.assertEqual(schema["title"], "Mock Registry Test Strategy Parameters")
        self.assertEqual(schema["type"], "object")
        self.assertIn("period", schema["properties"])
        self.assertIn("threshold", schema["properties"])
        self.assertIn("mode", schema["properties"])
        self.assertIn("enable_feature", schema["properties"])
        
        self.assertEqual(schema["properties"]["period"]["type"], "integer")
        self.assertEqual(schema["properties"]["period"]["minimum"], 10)
        self.assertEqual(schema["properties"]["period"]["maximum"], 50)
        
        self.assertEqual(schema["properties"]["threshold"]["type"], "number")
        self.assertEqual(schema["properties"]["threshold"]["minimum"], 1.0)
        self.assertEqual(schema["properties"]["threshold"]["maximum"], 5.0)
        
        self.assertEqual(schema["properties"]["mode"]["type"], "string")
        self.assertEqual(schema["properties"]["mode"]["enum"], ["fast", "slow"])

        self.assertEqual(schema["properties"]["enable_feature"]["type"], "boolean")

    def test_dynamic_register_from_code(self):
        strategy_code = """
from engine.strategy_registry.base import BaseStrategy, ParameterSpec, StrategyMetadata

class DynamicCustomStrategy(BaseStrategy):
    metadata = StrategyMetadata(
        name="Dynamic Custom Strategy",
        description="Dynamically compiled strategy for E2E test",
        regime_compatibility={"TRENDING_BULLISH": 95},
        preferred_timeframes=["ONE_MINUTE"],
        typical_holding_bars=12,
        requires_volume=True
    )
    parameter_specs = [
        ParameterSpec("param_x", "range_int", 5, 2, 10)
    ]
    def entry_rules(self, market_state): return True
    def exit_rules(self, market_state, position): return True
    def stop_loss(self, entry_price, current_price, direction): return False
    def take_profit(self, entry_price, current_price, direction): return False
    def position_size(self, capital, atr, price): return 1
    def get_param_grid(self, granularity="medium"): return {"param_x": [5]}
    def generate_code(self, symbol): return "pass"
"""
        # Register the code dynamically
        klass = StrategyRegistry.register_from_code(strategy_code)
        
        self.assertEqual(klass.metadata.name, "Dynamic Custom Strategy")
        
        # Verify it is stored and can be retrieved from StrategyRegistry
        retrieved_klass = StrategyRegistry.get("Dynamic Custom Strategy")
        self.assertIsNotNone(retrieved_klass)
        self.assertEqual(retrieved_klass.metadata.typical_holding_bars, 12)
        
        # Verify schema generation works for the dynamically registered strategy
        schema = retrieved_klass.get_parameter_schema()
        self.assertEqual(schema["title"], "Dynamic Custom Strategy Parameters")
        self.assertIn("param_x", schema["properties"])


if __name__ == "__main__":
    unittest.main()
