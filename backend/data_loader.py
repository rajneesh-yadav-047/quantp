"""
Multi-symbol data loader with Dataset Group support.

Integrates with SmartAPIClient for real data loading and
supports dataset group definitions from datasets/groups.yaml.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Groups config helpers
# ---------------------------------------------------------------------------

_GROUPS_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "datasets", "groups.yaml"
)


def load_groups_config(path: str = _GROUPS_CONFIG_PATH) -> Dict[str, List[str]]:
    """Load dataset groups from YAML configuration file."""
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    result: Dict[str, List[str]] = {}
    for k, v in cfg.items():
        if k == "custom_groups" and isinstance(v, dict):
            for ck, cv in (v or {}).items():
                result[ck] = list(cv or [])
        elif isinstance(v, list):
            result[k] = list(v)
    return result


def get_symbols_from_groups(groups: List[str], groups_config: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """Resolve a list of group names to a flat, deduplicated list of symbols."""
    if groups_config is None:
        groups_config = load_groups_config()
    symbols: List[str] = []
    seen: set = set()
    for grp in groups:
        for sym in groups_config.get(grp, []):
            if sym not in seen:
                seen.add(sym)
                symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# Multi-symbol data loading
# ---------------------------------------------------------------------------


def load_data(
    symbols: List[str],
    interval: str = "ONE_DAY",
    client=None,
) -> Dict[str, pd.DataFrame]:
    """
    Load data for multiple symbols using SmartAPIClient.

    Parameters
    ----------
    symbols : list of ticker symbols
    interval : data interval string (e.g. 'ONE_DAY', 'FIVE_MINUTE')
    client   : optional SmartAPIClient instance; created lazily if None

    Returns
    -------
    Dict mapping symbol -> DataFrame (None entries excluded)
    """
    if client is None:
        from backend.smartapi import SmartAPIClient
        client = SmartAPIClient()

    data: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            df = client.load_dataset_csv(sym.upper(), interval.upper())
            if df is not None and not df.empty:
                data[sym.upper()] = df
            else:
                print(f"WARN: No data for symbol {sym} @ {interval}")
        except Exception as e:
            print(f"ERROR: Failed to load {sym}: {e}")
    return data


def load_dataset_groups(
    selected_groups: Optional[List[str]] = None,
    additional_symbols: Optional[List[str]] = None,
    interval: str = "ONE_DAY",
    client=None,
) -> Dict[str, pd.DataFrame]:
    """
    Convenient entry point to load data for pre-defined groups and/or extra symbols.

    Parameters
    ----------
    selected_groups     : list of group names (e.g. ['BANKING_BASKET'])
    additional_symbols  : list of extra symbols to include
    interval            : data interval
    client              : optional SmartAPIClient

    Returns
    -------
    Dict mapping symbol -> DataFrame
    """
    groups_cfg = load_groups_config()
    symbols: List[str] = []

    if selected_groups:
        symbols.extend(get_symbols_from_groups(selected_groups, groups_cfg))
    if additional_symbols:
        symbols.extend(additional_symbols)

    # Deduplicate preserving order
    symbols = list(dict.fromkeys(s.upper() for s in symbols))
    return load_data(symbols, interval=interval, client=client)
