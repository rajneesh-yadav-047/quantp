"""
Example Multi-Asset Strategies.

Three ready-to-use templates demonstrating MultiAssetStrategy usage:
  1. PairTradingStrategy   – classic mean-reversion on spread z-score
  2. SectorRotationStrategy – momentum-based sector rotation
  3. StatArbStrategy       – cointegration-based statistical arbitrage
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from engine.runtime.multi_asset_strategy import MultiAssetStrategy
from engine.datamodels import MarketState


# ---------------------------------------------------------------------------
# 1. Pair Trading Strategy
# ---------------------------------------------------------------------------

class PairTradingStrategy(MultiAssetStrategy):
    """
    Classic pairs-trading on spread z-score.

    Parameters
    ----------
    sym1, sym2   : the two symbols
    lookback     : rolling window for mean/std of spread
    entry_z      : z-score threshold to enter (default 2.0)
    exit_z       : z-score to exit (default 0.5)
    qty          : shares to trade per side
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.sym1: str = self.parameters.get("sym1", "SBIN")
        self.sym2: str = self.parameters.get("sym2", "HDFCBANK")
        self.lookback: int = int(self.parameters.get("lookback", 20))
        self.entry_z: float = float(self.parameters.get("entry_z", 2.0))
        self.exit_z: float = float(self.parameters.get("exit_z", 0.5))
        self.qty: int = int(self.parameters.get("qty", 10))
        self._spreads: List[float] = []

    def on_tick(self, state: MarketState) -> None:
        p1 = self.price(self.sym1)
        p2 = self.price(self.sym2)
        if p1 == 0 or p2 == 0:
            return

        spread = p1 - p2
        self._spreads.append(spread)
        if len(self._spreads) > self.lookback * 3:
            self._spreads = self._spreads[-self.lookback * 3:]

        if len(self._spreads) < self.lookback:
            return

        window = self._spreads[-self.lookback:]
        mu = float(np.mean(window))
        sigma = float(np.std(window))
        if sigma == 0:
            return

        z = (spread - mu) / sigma
        pos1 = self.position(self.sym1)
        pos2 = self.position(self.sym2)
        in_position = pos1 != 0 or pos2 != 0

        # Entry
        if not in_position:
            if z > self.entry_z:
                # Spread too high → short sym1, long sym2
                self.sell(self.sym1, self.qty, tag="pair_entry_short")
                self.buy(self.sym2, self.qty, tag="pair_entry_long")
                self.log(f"PAIR ENTRY: short {self.sym1}, long {self.sym2} @ z={z:.2f}")
            elif z < -self.entry_z:
                # Spread too low → long sym1, short sym2
                self.buy(self.sym1, self.qty, tag="pair_entry_long")
                self.sell(self.sym2, self.qty, tag="pair_entry_short")
                self.log(f"PAIR ENTRY: long {self.sym1}, short {self.sym2} @ z={z:.2f}")
        # Exit
        elif abs(z) < self.exit_z:
            if pos1 > 0:
                self.sell(self.sym1, abs(pos1), tag="pair_exit")
            elif pos1 < 0:
                self.buy(self.sym1, abs(pos1), tag="pair_exit")
            if pos2 > 0:
                self.sell(self.sym2, abs(pos2), tag="pair_exit")
            elif pos2 < 0:
                self.buy(self.sym2, abs(pos2), tag="pair_exit")
            self.log(f"PAIR EXIT: z={z:.2f}")


# ---------------------------------------------------------------------------
# 2. Sector Rotation Strategy
# ---------------------------------------------------------------------------

class SectorRotationStrategy(MultiAssetStrategy):
    """
    Momentum-based sector rotation.

    Ranks all symbols by their N-bar momentum and rotates into the top K,
    exiting positions in the bottom-ranked symbols.

    Parameters
    ----------
    momentum_window : lookback for momentum calculation (default 20)
    top_k           : number of symbols to hold long (default 2)
    qty_per_symbol  : shares per position (default 10)
    rebalance_every : rebalance every N bars (default 5)
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.momentum_window: int = int(self.parameters.get("momentum_window", 20))
        self.top_k: int = int(self.parameters.get("top_k", 2))
        self.qty_per_symbol: int = int(self.parameters.get("qty_per_symbol", 10))
        self.rebalance_every: int = int(self.parameters.get("rebalance_every", 5))
        self._tick_count: int = 0

    def _momentum(self, sym: str) -> float:
        hist = self.history(sym, self.momentum_window + 1)
        if len(hist) < 2:
            return 0.0
        prices = [c.close for c in hist]
        return (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0.0

    def on_tick(self, state: MarketState) -> None:
        self._tick_count += 1
        if self._tick_count % self.rebalance_every != 0:
            return

        syms = self.symbols()
        if not syms:
            return

        # Rank by momentum
        scores = [(sym, self._momentum(sym)) for sym in syms]
        scores.sort(key=lambda x: x[1], reverse=True)
        top_symbols = {sym for sym, _ in scores[: self.top_k]}

        # Exit positions in non-top symbols
        for sym in syms:
            pos = self.position(sym)
            if pos > 0 and sym not in top_symbols:
                self.sell(sym, abs(pos), tag="rotation_exit")
                self.log(f"ROTATION EXIT: {sym}")

        # Enter top symbols
        for sym in top_symbols:
            if self.position(sym) == 0:
                self.buy(sym, self.qty_per_symbol, tag="rotation_enter")
                self.log(f"ROTATION ENTER: {sym} (momentum={self._momentum(sym):.4f})")


# ---------------------------------------------------------------------------
# 3. Statistical Arbitrage Strategy (Residual Mean-Reversion)
# ---------------------------------------------------------------------------

class StatArbStrategy(MultiAssetStrategy):
    """
    Statistical arbitrage using residuals from a linear factor model.

    Computes rolling OLS residuals of each stock against a 'market' proxy
    (first symbol in the list) and mean-reverts on the residual z-score.

    Parameters
    ----------
    market_proxy  : symbol used as the market factor (default first symbol)
    lookback      : rolling regression window (default 30)
    entry_z       : residual z-score to enter (default 1.5)
    exit_z        : residual z-score to exit (default 0.3)
    qty           : shares per position (default 5)
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.market_proxy: Optional[str] = self.parameters.get("market_proxy")
        self.lookback: int = int(self.parameters.get("lookback", 30))
        self.entry_z: float = float(self.parameters.get("entry_z", 1.5))
        self.exit_z: float = float(self.parameters.get("exit_z", 0.3))
        self.qty: int = int(self.parameters.get("qty", 5))
        self._residual_history: Dict[str, List[float]] = {}

    def _get_residual_zscore(self, sym: str, mkt_sym: str) -> Optional[float]:
        hist_sym = self.history(sym, self.lookback + 1)
        hist_mkt = self.history(mkt_sym, self.lookback + 1)
        n = min(len(hist_sym), len(hist_mkt), self.lookback + 1)
        if n < 10:
            return None

        p_sym = np.array([c.close for c in hist_sym[-n:]], dtype=float)
        p_mkt = np.array([c.close for c in hist_mkt[-n:]], dtype=float)

        # OLS: p_sym = alpha + beta * p_mkt + residual
        X = np.column_stack([np.ones(n), p_mkt])
        try:
            beta_hat = np.linalg.lstsq(X, p_sym, rcond=None)[0]
        except np.linalg.LinAlgError:
            return None

        residuals = p_sym - (beta_hat[0] + beta_hat[1] * p_mkt)
        mu, sigma = float(np.mean(residuals)), float(np.std(residuals))
        if sigma == 0:
            return None
        return float((residuals[-1] - mu) / sigma)

    def on_tick(self, state: MarketState) -> None:
        syms = self.symbols()
        if not syms:
            return

        mkt_sym = self.market_proxy or syms[0]
        tradeable = [s for s in syms if s != mkt_sym]

        for sym in tradeable:
            z = self._get_residual_zscore(sym, mkt_sym)
            if z is None:
                continue

            pos = self.position(sym)

            if pos == 0:
                if z > self.entry_z:
                    self.sell(sym, self.qty, tag="statarb_short")
                    self.log(f"STATARB SHORT: {sym} @ z={z:.2f}")
                elif z < -self.entry_z:
                    self.buy(sym, self.qty, tag="statarb_long")
                    self.log(f"STATARB LONG: {sym} @ z={z:.2f}")
            elif abs(z) < self.exit_z:
                if pos > 0:
                    self.sell(sym, abs(pos), tag="statarb_exit")
                else:
                    self.buy(sym, abs(pos), tag="statarb_exit")
                self.log(f"STATARB EXIT: {sym} @ z={z:.2f}")
