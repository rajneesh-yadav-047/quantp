"""
Shared sandbox compiler for strategy runtimes.

Eliminates duplication between ProsperityRuntime and LegacyRuntime
by providing a single sandbox compilation utility.
"""

import json
from typing import Dict, Any, Optional


class SandboxCompiler:
    """
    Compiles strategy code in a restricted sandboxed namespace.
    
    Provides:
    - Safe builtins (no os, sys, file I/O)
    - Allowed module imports (math, statistics, json, pandas, numpy)
    - Parameter injection for optimization sweeps
    - Runtime class/func detection for auto-routing
    """

    ALLOWED_MODULES = {"math", "statistics", "json", "pandas", "numpy", "typing", "collections", "itertools"}

    SAFE_BUILTINS = {
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

    @classmethod
    def build_sandbox(
        cls,
        parameters: Optional[Dict[str, Any]] = None,
        extra_globals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a sandboxed namespace with safe builtins and allowed imports.
        
        Args:
            parameters: optional parameter overrides injected into namespace
            extra_globals: additional globals to inject (e.g. Logger, Order classes)
            
        Returns:
            dict suitable as exec() globals
        """
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in cls.ALLOWED_MODULES:
                return __import__(name, globals, locals, fromlist, level)
            raise ImportError(f"Import of module '{name}' is restricted in the sandboxed runtime.")

        sandbox = {
            '__builtins__': {**cls.SAFE_BUILTINS, '__import__': safe_import},
            '__name__': '<strategy>',
            'json': json,
            'math': __import__('math'),
            'statistics': __import__('statistics'),
        }

        if extra_globals:
            sandbox.update(extra_globals)

        if parameters:
            sandbox.update(parameters)

        return sandbox

    @classmethod
    def compile_strategy(
        cls,
        strategy_code: str,
        parameters: Optional[Dict[str, Any]] = None,
        extra_globals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Compile strategy code and return the sandbox namespace.
        
        Args:
            strategy_code: full source code of the strategy
            parameters: optional parameter overrides
            extra_globals: additional globals to inject
            
        Returns:
            sandbox namespace dict containing compiled classes/functions
            
        Raises:
            RuntimeError: if compilation fails
        """
        sandbox = cls.build_sandbox(parameters, extra_globals)
        try:
            exec(strategy_code, sandbox)
        except Exception as e:
            raise RuntimeError(f"Strategy compilation error: {e}")
        return sandbox

    @staticmethod
    def detect_runtime_type(strategy_code: str) -> str:
        """
        Auto-detect whether strategy uses Prosperity or Legacy interface.
        
        Returns:
            'prosperity_trader' or 'legacy_on_bar'
        """
        if "class Trader" in strategy_code and "def run" in strategy_code:
            return "prosperity_trader"
        elif "def on_bar" in strategy_code:
            return "legacy_on_bar"
        else:
            return "prosperity_trader"  # default to stricter
