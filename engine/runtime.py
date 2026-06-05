import sys
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from engine.datamodels import MarketState, OrderRequest, Candle, Position, Portfolio, Order

class SandboxedStrategyRuntime:
    def __init__(self, code_content: str, parameters: Optional[Dict[str, Any]] = None):
        self.code_content = code_content
        self.parameters = parameters or {}
        self.log_buffer: List[str] = []
        self.strategy_instance: Any = None
        self._compile_and_initialize()

    def _compile_and_initialize(self):
        """Compiles user code and instantiates the Strategy class inside a sandboxed environment."""
        import builtins
        
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            allowed = ["math", "numpy", "pandas", "json", "datetime"]
            if name in allowed:
                return builtins.__import__(name, globals, locals, fromlist, level)
            raise ImportError(f"Import of module '{name}' is restricted in the sandboxed runtime.")

        # Define clean built-ins
        safe_builtins = {
            'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
            'chr': chr, 'dict': dict, 'divmod': divmod, 'enumerate': enumerate,
            'filter': filter, 'float': float, 'format': format, 'hash': hash,
            'hex': hex, 'id': id, 'int': int, 'isinstance': isinstance,
            'issubclass': issubclass, 'iter': iter, 'len': len, 'list': list,
            'map': map, 'max': max, 'min': min, 'next': next, 'oct': oct,
            'ord': ord, 'pow': pow, 'range': range, 'repr': repr,
            'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
            'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
            'type': type, 'zip': zip,
            'print': self._custom_print,
            '__build_class__': builtins.__build_class__,
            '__import__': safe_import,
            'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
            'KeyError': KeyError, 'IndexError': IndexError, 'AttributeError': AttributeError,
        }

        # Expose math, numpy, and domain models
        sandbox_globals = {
            '__name__': '<strategy>',
            '__builtins__': safe_builtins,
            'math': math,
            'np': np,
            'numpy': np,
            'pd': pd,
            'pandas': pd,
            'Candle': Candle,
            'OrderRequest': OrderRequest,
            'Order': Order,
            'Position': Position,
            'Portfolio': Portfolio,
            'MarketState': MarketState,
        }

        try:
            # Compile code
            compiled_code = compile(self.code_content, '<strategy>', 'exec')
            # Run code within globals
            exec(compiled_code, sandbox_globals)
        except Exception as e:
            raise RuntimeError(f"Compilation/Initialization Error: {str(e)}")

        # Find Strategy class in globals
        if 'Strategy' not in sandbox_globals:
            raise AttributeError("Your code must define a class named 'Strategy'.")

        try:
            self.strategy_instance = sandbox_globals['Strategy']()
            if self.parameters:
                for k, v in self.parameters.items():
                    setattr(self.strategy_instance, k, v)
                    if hasattr(self.strategy_instance, 'parameters') and isinstance(self.strategy_instance.parameters, dict):
                        self.strategy_instance.parameters[k] = v
        except Exception as e:
            raise RuntimeError(f"Error instantiating Strategy class: {str(e)}")

    def _custom_print(self, *args, **kwargs):
        """Captures stdout from strategy execution."""
        msg = " ".join(str(arg) for arg in args)
        self.log_buffer.append(msg)

    def on_bar(self, state: MarketState) -> List[OrderRequest]:
        """Invokes on_bar on the user strategy, safety checks orders, and returns them."""
        self.log_buffer.clear()
        if not self.strategy_instance:
            raise RuntimeError("Strategy not initialized.")

        # Ensure on_bar is defined
        if not hasattr(self.strategy_instance, 'on_bar'):
            raise AttributeError("Strategy class must implement 'on_bar(self, state: MarketState)' method.")

        try:
            # Call strategy method
            raw_orders = self.strategy_instance.on_bar(state)
        except Exception as e:
            self.log_buffer.append(f"Runtime Error in on_bar: {str(e)}")
            return []

        # Convert and validate orders
        validated_orders: List[OrderRequest] = []
        if not raw_orders:
            return []

        if not isinstance(raw_orders, list):
            raw_orders = [raw_orders]

        for idx, item in enumerate(raw_orders):
            try:
                if isinstance(item, OrderRequest):
                    validated_orders.append(item)
                elif isinstance(item, dict):
                    # Construct OrderRequest from dict
                    validated_orders.append(OrderRequest(**item))
                else:
                    self.log_buffer.append(f"Warning: Discarded order at index {idx} - must be OrderRequest or dict.")
            except Exception as ex:
                self.log_buffer.append(f"Warning: Failed to parse order at index {idx} due to error: {str(ex)}")

        return validated_orders

    def get_logs(self) -> List[str]:
        """Returns the printed logs from the last step run."""
        return list(self.log_buffer)
