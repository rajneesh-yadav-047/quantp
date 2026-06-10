"""
Prosperity-compatible strategy runtime.

Implements the Trader.run(state) -> (orders, conversions, traderData) contract.

Key responsibilities:
1. Execute user code in a sandboxed environment
2. Accept TradingState, call trader.run(state)
3. Capture submitted orders and trader_data updates
4. Route strategy logs through Logger
5. Maintain backward compatibility with legacy on_bar strategies
"""

import json
import sys
from io import StringIO
from typing import List, Dict, Any, Optional, Tuple
from contextlib import redirect_stdout

from engine.runtime.datamodels import (
    Order, TradingState, Logger, OrderType
)


class ProsperityRuntime:
    """
    Executes Prosperity-style trader.py strategies.
    
    Contract:
        orders, conversions, trader_data = trader.run(state)
    
    Where:
        - state: TradingState
        - orders: List[Order]
        - conversions: Dict[str, int] (unused in QuantLab for now)
        - trader_data: str (JSON-serialized strategy memory)
    """

    def __init__(self, strategy_code: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Args:
            strategy_code: full trader.py source code
            parameters: optional parameter overrides (for optimization)
        """
        self.strategy_code = strategy_code
        self.parameters = parameters or {}
        self.sandbox = {}
        self.logger = Logger()
        self.captured_output = StringIO()
        self._compile_strategy()

    def _compile_strategy(self):
        """Compile strategy code in a sandboxed namespace."""
        allowed_modules = {"math", "statistics", "json", "pandas", "numpy"}
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in allowed_modules:
                return __import__(name, globals, locals, fromlist, level)
            raise ImportError(f"Import of module '{name}' is restricted in the sandboxed runtime.")

        safe_builtins = {
            'print': print,
            'len': len,
            'range': range,
            'list': list,
            'dict': dict,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'round': round,
            'sorted': sorted,
            '__build_class__': __import__('builtins').__build_class__,
            '__import__': safe_import,
            'hasattr': hasattr,
            'getattr': getattr,
            'setattr': setattr,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'enumerate': enumerate,
            'zip': zip,
            'filter': filter,
            'map': map,
            'type': type,
            'Exception': Exception,
            'ValueError': ValueError,
            'KeyError': KeyError,
            'IndexError': IndexError,
            'AttributeError': AttributeError,
        }

        self.sandbox = {
            '__builtins__': safe_builtins,
            '__name__': '<strategy>',
            'json': json,
            'math': __import__('math'),
            'statistics': __import__('statistics'),
            'Logger': Logger,
            'Order': Order,
            'OrderType': OrderType,
        }

        # Inject parameters if provided
        for key, value in self.parameters.items():
            self.sandbox[key] = value

        try:
            exec(self.strategy_code, self.sandbox)
        except Exception as e:
            raise RuntimeError(f"Strategy compilation error: {e}")

    def on_tick(self, state: TradingState) -> Tuple[List[Order], str]:
        """
        Execute strategy for a single tick.

        Args:
            state: TradingState with market data and portfolio state

        Returns:
            (orders_list, updated_trader_data_json)
        """
        self.logger.clear()

        try:
            # Capture stdout for debugging
            captured = StringIO()
            with redirect_stdout(captured):
                # Call trader.run(state)
                trader_class = self.sandbox.get('Trader')
                if not trader_class:
                    raise RuntimeError("Trader class not found in strategy code")

                # Instantiate and call run(state)
                instance = trader_class()
                result = instance.run(state)

        except Exception as e:
            self.logger.record("error", message=str(e))
            # Return empty orders and preserve trader_data
            return [], state.trader_data

        # Unpack result
        if isinstance(result, tuple):
            orders, conversions, trader_data_str = result
        else:
            # Fallback: assume dict-like
            orders = result.get('orders', [])
            trader_data_str = result.get('trader_data', state.trader_data)

        # Capture any stdout
        stdout_content = captured.getvalue()
        if stdout_content:
            self.logger.print(stdout_content.strip())

        # Normalize orders to Order objects
        normalized_orders = []

        # Handle dict-based order structure (Standard Prosperity: {symbol: [Order]})
        if isinstance(orders, dict):
            flat_orders = []
            for symbol_orders in orders.values():
                if isinstance(symbol_orders, list):
                    flat_orders.extend(symbol_orders)
            orders = flat_orders

        for order in orders:
            if isinstance(order, Order):
                normalized_orders.append(order)
            elif isinstance(order, dict):
                normalized_orders.append(Order(**order))
            # else skip invalid orders

        return normalized_orders, trader_data_str

    def get_logs(self) -> str:
        """
        Get accumulated logs as JSON string.
        
        Returns: JSON-encoded list of log entries (one per flush)
        """
        return self.logger.flush()

    def get_log_entries(self) -> List[Dict[str, Any]]:
        """Get raw log entries without flushing."""
        return self.logger.get_logs()


class LegacyRuntime:
    """
    Backward-compatible runtime for existing on_bar strategies.
    
    Wraps the legacy on_bar(state) -> List[OrderRequest] interface
    and adapts it to the Prosperity contract.
    
    Allows gradual migration without breaking existing strategies.
    """

    def __init__(self, strategy_code: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Args:
            strategy_code: strategy code with on_bar(state) function
            parameters: optional parameter overrides
        """
        self.strategy_code = strategy_code
        self.parameters = parameters or {}
        self.sandbox = {}
        self.logger = Logger()
        self._compile_strategy()

    def _compile_strategy(self):
        """Compile legacy strategy code."""
        allowed_modules = {"math", "statistics", "json", "pandas", "numpy"}
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in allowed_modules:
                return __import__(name, globals, locals, fromlist, level)
            raise ImportError(f"Import of module '{name}' is restricted in the sandboxed runtime.")

        safe_builtins = {
            'print': print,
            'len': len,
            'range': range,
            'list': list,
            'dict': dict,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'round': round,
            'sorted': sorted,
            '__build_class__': __import__('builtins').__build_class__,
            '__import__': safe_import,
            'hasattr': hasattr,
            'getattr': getattr,
            'setattr': setattr,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'enumerate': enumerate,
            'zip': zip,
            'filter': filter,
            'map': map,
            'type': type,
            'Exception': Exception,
            'ValueError': ValueError,
            'KeyError': KeyError,
            'IndexError': IndexError,
            'AttributeError': AttributeError,
        }

        self.sandbox = {
            '__builtins__': safe_builtins,
            '__name__': '<strategy>',
            'json': json,
            'math': __import__('math'),
            'statistics': __import__('statistics'),
        }

        for key, value in self.parameters.items():
            self.sandbox[key] = value

        try:
            exec(self.strategy_code, self.sandbox)
        except Exception as e:
            raise RuntimeError(f"Legacy strategy compilation error: {e}")

    def on_bar(self, state: Any) -> List[Dict[str, Any]]:
        """
        Execute legacy on_bar strategy.

        Args:
            state: can be MarketState or TradingState (both work)

        Returns:
            List of order dicts/objects
        """
        self.logger.clear()

        try:
            # Legacy strategies define either:
            #   class Strategy: def on_bar(self, state): ...
            # or a top-level: def on_bar(state): ...
            strategy_class = self.sandbox.get('Strategy')
            on_bar_func = self.sandbox.get('on_bar')

            if strategy_class and hasattr(strategy_class, 'on_bar'):
                instance = strategy_class()
                result = instance.on_bar(state)
            elif on_bar_func:
                result = on_bar_func(state)
            else:
                raise RuntimeError("on_bar function not found in strategy code")

            if not isinstance(result, list):
                result = []

        except Exception as e:
            self.logger.record("error", message=str(e))
            result = []

        return result

    def on_tick(self, state: Any) -> Tuple[List[Order], str]:
        """
        Adapter that wraps on_bar for compatibility with BacktestEngine.

        Accepts TradingState or MarketState, calls on_bar, normalizes
        legacy dict orders (with 'qty' key) to Order objects.

        Returns:
            (orders_list, trader_data_json)
        """
        self.logger.clear()

        try:
            # Legacy strategies define either:
            #   class Strategy: def on_bar(self, state): ...
            # or a top-level: def on_bar(state): ...
            strategy_class = self.sandbox.get('Strategy')
            on_bar_func = self.sandbox.get('on_bar')

            if strategy_class and hasattr(strategy_class, 'on_bar'):
                instance = strategy_class()
                result = instance.on_bar(state)
            elif on_bar_func:
                result = on_bar_func(state)
            else:
                raise RuntimeError("on_bar function not found in strategy code")

            if not isinstance(result, list):
                result = []

        except Exception as e:
            self.logger.record("error", message=str(e))
            result = []

        # Normalize legacy dict orders to Order objects
        normalized_orders = []
        for order in result:
            if isinstance(order, Order):
                normalized_orders.append(order)
            elif isinstance(order, dict):
                order_dict = dict(order)
                # Legacy uses 'qty', Prosperity/Order uses 'quantity'
                if 'qty' in order_dict and 'quantity' not in order_dict:
                    order_dict['quantity'] = order_dict.pop('qty')
                # Filter to only keys Order dataclass accepts
                allowed_keys = {'symbol', 'direction', 'price', 'quantity', 'type', 'order_id'}
                filtered = {k: v for k, v in order_dict.items() if k in allowed_keys}
                normalized_orders.append(Order(**filtered))
            # else skip invalid orders

        return normalized_orders, state.trader_data if hasattr(state, 'trader_data') else "{}"

    def get_logs(self) -> str:
        """Get accumulated logs as JSON string."""
        return self.logger.flush()

    def get_log_entries(self) -> List[Dict[str, Any]]:
        """Get raw log entries."""
        return self.logger.get_logs()


class RuntimeFactory:
    """
    Factory for creating the appropriate runtime based on strategy type.
    
    Detects strategy interface and instantiates:
    - ProsperityRuntime for trader.py (class Trader with run method)
    - LegacyRuntime for on_bar strategies
    """

    @staticmethod
    def create_runtime(
        strategy_code: str,
        runtime_type: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Create appropriate runtime instance.

        Args:
            strategy_code: source code
            runtime_type: "prosperity_trader", "legacy_on_bar", or None for auto-detect
            parameters: optional parameter overrides

        Returns:
            ProsperityRuntime or LegacyRuntime instance
        """
        if runtime_type == "prosperity_trader":
            return ProsperityRuntime(strategy_code, parameters)
        elif runtime_type == "legacy_on_bar":
            return LegacyRuntime(strategy_code, parameters)
        else:
            # Auto-detect
            if "class Trader" in strategy_code and "def run" in strategy_code:
                return ProsperityRuntime(strategy_code, parameters)
            elif "def on_bar" in strategy_code:
                return LegacyRuntime(strategy_code, parameters)
            else:
                # Default to Prosperity (stricter)
                return ProsperityRuntime(strategy_code, parameters)
