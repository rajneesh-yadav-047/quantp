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
from io import StringIO
from typing import List, Dict, Any, Optional, Tuple
from contextlib import redirect_stdout

from engine.runtime.sandbox import SandboxCompiler
from engine.runtime.datamodels import (
    Order, TradingState, Logger
)


class ProsperityRuntime:
    """
    Executes Prosperity-style trader.py strategies.

    Contract:
        orders, conversions, trader_data = trader.run(state)
    """

    def __init__(self, strategy_code: str, parameters: Optional[Dict[str, Any]] = None):
        self.strategy_code = strategy_code
        self.parameters = parameters or {}
        self.logger = Logger()
        self.captured_output = StringIO()
        self.sandbox = SandboxCompiler.compile_strategy(
            strategy_code=strategy_code,
            parameters=parameters,
            extra_globals={
                'Logger': Logger,
                'Order': Order,
            },
        )

    def on_tick(self, state: TradingState) -> Tuple[List[Order], str]:
        """
        Execute strategy for a single tick.

        Returns:
            (orders_list, updated_trader_data_json)
        """
        self.logger.clear()

        try:
            captured = StringIO()
            with redirect_stdout(captured):
                trader_class = self.sandbox.get('Trader')
                if not trader_class:
                    raise RuntimeError("Trader class not found in strategy code")
                instance = trader_class()
                result = instance.run(state)
        except Exception as e:
            self.logger.record("error", message=str(e))
            return [], state.trader_data

        # Unpack result
        if isinstance(result, tuple):
            orders, conversions, trader_data_str = result
        else:
            orders = result.get('orders', [])
            trader_data_str = result.get('trader_data', state.trader_data)

        stdout_content = captured.getvalue()
        if stdout_content:
            self.logger.print(stdout_content.strip())

        # Normalize orders
        normalized_orders = []
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

        return normalized_orders, trader_data_str

    def get_logs(self) -> str:
        """Get accumulated logs as JSON string."""
        return self.logger.flush()

    def get_log_entries(self) -> List[Dict[str, Any]]:
        """Get raw log entries without flushing."""
        return self.logger.get_logs()


class LegacyRuntime:
    """
    Backward-compatible runtime for existing on_bar strategies.

    Wraps the legacy on_bar(state) -> List[OrderRequest] interface
    and adapts it to the Prosperity contract.
    """

    def __init__(self, strategy_code: str, parameters: Optional[Dict[str, Any]] = None):
        self.strategy_code = strategy_code
        self.parameters = parameters or {}
        self.logger = Logger()
        self.sandbox = SandboxCompiler.compile_strategy(
            strategy_code=strategy_code,
            parameters=parameters,
        )

    def on_tick(self, state: Any) -> Tuple[List[Order], str]:
        """
        Adapter that wraps on_bar for compatibility with BacktestEngine.

        Returns:
            (orders_list, trader_data_json)
        """
        self.logger.clear()

        try:
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
                if 'qty' in order_dict and 'quantity' not in order_dict:
                    order_dict['quantity'] = order_dict.pop('qty')
                allowed_keys = {'symbol', 'direction', 'price', 'quantity', 'type', 'order_id'}
                filtered = {k: v for k, v in order_dict.items() if k in allowed_keys}
                normalized_orders.append(Order(**filtered))

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
            detected = SandboxCompiler.detect_runtime_type(strategy_code)
            if detected == "prosperity_trader":
                return ProsperityRuntime(strategy_code, parameters)
            else:
                return LegacyRuntime(strategy_code, parameters)
