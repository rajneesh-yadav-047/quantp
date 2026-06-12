"""
Mock Deployment Engine: Live paper trading with real market data.

This module provides a complete live mock trading environment that:
1. Consumes real-time market data from SmartAPI (polling-based live feed)
2. Runs strategy code via the existing RuntimeFactory + SandboxCompiler
3. Simulates order execution via ExecutionSimulator (NO REAL ORDERS PLACED)
4. Tracks portfolio, positions, and PnL in real-time
5. Optionally uses SmartAPI charges calculation for realistic fee simulation
6. Persists all trades, PnL snapshots, and events to the database
7. Streams updates via SSE to the frontend

NO REAL MONEY IS EVER USED. ALL ORDERS ARE SIMULATED.
"""

import asyncio
import json
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
import pandas as pd

from sqlalchemy.orm import Session
from engine.datamodels import Candle, MarketState, Order
from engine.execution import ExecutionSimulator
from engine.portfolio import PortfolioManager
from engine.order_manager import OrderManager
from engine.runtime.runtimes import RuntimeFactory, LegacyRuntime
from engine.runtime.adapters import CandleToOrderBookAdapter, PortfolioStateBuilder
from engine.runtime.datamodels import TradingState, Trade as RTrade
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.market_data_service import MarketDataService, ensure_market_data_service
from backend.services.redis_client import get_latest_tick, get_latest_candle
from backend.database import (
    DeploymentDB, LiveTradeDB, LivePnLSnapshotDB, DeploymentEventDB,
    StrategyDB, SessionLocal
)


class DeploymentRunner:
    """
    Individual runner for a single mock deployment.
    
    Each runner is an asyncio task that polls live market data,
    executes the strategy, simulates fills, and logs everything.
    """
    
    def __init__(
        self,
        deployment_id: str,
        strategy: StrategyDB,
        symbol: str,
        interval: str,
        initial_capital: float,
        max_position_size: Optional[int] = None,
        slippage_pct: float = 0.0,  # 0 slippage for paper mode by default
        trade_type: str = "INTRADAY",
        use_real_charges: bool = True,
        poll_interval_seconds: Optional[int] = None,
    ):
        self.deployment_id = deployment_id
        self.strategy = strategy
        self.symbol = symbol
        self.interval = interval
        self.initial_capital = initial_capital
        self.max_position_size = max_position_size
        self.slippage_pct = slippage_pct
        self.trade_type = trade_type
        self.use_real_charges = use_real_charges
        
        # Determine poll interval based on candle interval if not specified
        # With Redis + WebSocket, we poll frequently to check for new ticks
        if poll_interval_seconds is None:
            if interval == "ONE_MINUTE":
                poll_interval_seconds = 5   # Fast poll for 1m
            elif interval == "FIVE_MINUTE":
                poll_interval_seconds = 10  # Fast poll for 5m
            elif interval == "FIFTEEN_MINUTE":
                poll_interval_seconds = 15
            elif interval == "ONE_HOUR":
                poll_interval_seconds = 30
            elif interval == "ONE_DAY":
                poll_interval_seconds = 60
            else:
                poll_interval_seconds = 10
        self.poll_interval_seconds = poll_interval_seconds
        
        # Subscribe to Market Data Service for real-time ticks
        self._mds_subscribed = False
        self._last_processed_tick_timestamp = None
        self._last_tick_ltp = None
        
        # Execution components
        self.execution_sim = ExecutionSimulator(
            slippage_pct=slippage_pct,
            default_trade_type=trade_type
        )
        self.portfolio_mgr = PortfolioManager(
            initial_capital=initial_capital,
            default_trade_type=trade_type,
            execution_sim=self.execution_sim,
        )
        self.order_mgr = OrderManager(
            execution_sim=self.execution_sim,
            max_position_size=max_position_size,
        )
        self.order_book_adapter = CandleToOrderBookAdapter(spread_pct=0.01, depth_size=100)
        
        # Strategy runtime
        parameters = json.loads(strategy.parameters_json) if strategy.parameters_json else None
        self.runtime = RuntimeFactory.create_runtime(
            strategy_code=strategy.code or "",
            runtime_type=getattr(strategy, 'runtime_type', 'legacy_on_bar'),
            parameters=parameters,
        )
        
        # State
        self.status = "running"  # running, paused, stopped
        self.task: Optional[asyncio.Task] = None
        self.step = 0
        self.trader_data_json = "{}"
        self.historical_candles: List[Candle] = []
        self.own_trades: List[RTrade] = []
        self.current_prices: Dict[str, float] = {}
        self._stop_event = asyncio.Event()
        self._callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # SmartAPI client for live data
        self.smartapi_client: Optional[SmartAPIClient] = None
        if SmartAPIManager.is_connected():
            self.smartapi_client = SmartAPIManager.get_client()
        elif SmartAPIManager.is_configured():
            fresh = SmartAPIManager.create_fresh_client()
            if fresh.connect():
                SmartAPIManager.set_client(fresh)
                self.smartapi_client = fresh
    
    def add_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a callback for real-time events. callback(event_type, data)"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify(self, event_type: str, data: Dict[str, Any]):
        for cb in self._callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass
    
    def _db_session(self) -> Session:
        return SessionLocal()
    
    def _log_event(self, event_type: str, message: str, data: Optional[Dict] = None):
        """Persist a deployment event to the database."""
        try:
            db = self._db_session()
            event = DeploymentEventDB(
                deployment_id=self.deployment_id,
                event_type=event_type,
                message=message,
                data_json=json.dumps(data) if data else None,
            )
            db.add(event)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[DeploymentRunner] Failed to log event: {e}")
    
    def _save_trade(self, trade: Any):
        """Persist a filled trade to the database."""
        try:
            db = self._db_session()
            
            # Get charges from SmartAPI if available and configured
            charges_source = "calculated"
            charges_data = {
                "brokerage": getattr(trade, 'brokerage', 0.0),
                "stt": getattr(trade, 'stt', 0.0),
                "exc_charges": getattr(trade, 'exc_charges', 0.0),
                "gst": getattr(trade, 'gst', 0.0),
                "sebi_charges": getattr(trade, 'sebi_charges', 0.0),
                "stamp_duty": getattr(trade, 'stamp_duty', 0.0),
                "total_charges": getattr(trade, 'total_charges', 0.0),
            }
            
            if self.use_real_charges and self.smartapi_client:
                try:
                    api_charges = self.smartapi_client.calculate_charges_api(
                        symbol=trade.symbol,
                        direction=trade.direction,
                        price=trade.price,
                        qty=trade.qty,
                        trade_type=self.trade_type,
                    )
                    if api_charges:
                        charges_data = api_charges
                        charges_source = "api"
                except Exception:
                    pass
            
            live_trade = LiveTradeDB(
                deployment_id=self.deployment_id,
                strategy_id=self.strategy.id,
                symbol=trade.symbol,
                direction=trade.direction,
                price=trade.price,
                qty=trade.qty,
                value=trade.price * trade.qty,
                brokerage=charges_data["brokerage"],
                stt=charges_data["stt"],
                exc_charges=charges_data["exchange_charges"],
                gst=charges_data["gst"],
                sebi_charges=charges_data["sebi_charges"],
                stamp_duty=charges_data["stamp_duty"],
                total_charges=charges_data["total_charges"],
                charges_source=charges_source,
            )
            db.add(live_trade)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[DeploymentRunner] Failed to save trade: {e}")
    
    def _save_pnl_snapshot(self):
        """Persist a PnL snapshot to the database."""
        try:
            db = self._db_session()
            snapshot = self.portfolio_mgr.get_snapshot()
            positions_json = json.dumps({
                sym: {
                    "qty": pos.qty,
                    "avg_price": pos.avg_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for sym, pos in self.portfolio_mgr.portfolio.positions.items()
            })
            
            pnl = LivePnLSnapshotDB(
                deployment_id=self.deployment_id,
                strategy_id=self.strategy.id,
                cash=snapshot["cash"],
                equity=snapshot["equity"],
                unrealized_pnl=snapshot.get("unrealized_pnl", 0.0),
                realized_pnl=sum(p.realized_pnl for p in self.portfolio_mgr.portfolio.positions.values()),
                total_fees=snapshot["total_fees"],
                total_pnl=snapshot["total_pnl"],
                margin_used=snapshot.get("margin_used", 0.0),
                margin_free=snapshot.get("margin_free", 0.0),
                position_count=len(self.portfolio_mgr.portfolio.positions),
                total_qty=sum(abs(p.qty) for p in self.portfolio_mgr.portfolio.positions.values()),
                positions_json=positions_json,
            )
            db.add(pnl)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[DeploymentRunner] Failed to save PnL snapshot: {e}")
    
    async def _subscribe_to_market_data(self):
        """Subscribe this symbol to the centralized Market Data Service."""
        if self._mds_subscribed:
            return
        try:
            mds = await ensure_market_data_service([self.symbol])
            self._mds_subscribed = True
            print(f"[DeploymentRunner] Subscribed {self.symbol} to Market Data Service.")
        except Exception as e:
            print(f"[DeploymentRunner] Market Data Service subscription failed: {e}")
    
    async def _fetch_live_candle(self) -> Optional[Dict[str, Any]]:
        """Fetch the latest live candle from Redis ONLY. No REST or mock fallbacks."""
        # Map strategy interval to MDS interval format
        interval_map = {
            "ONE_MINUTE": "1m",
            "FIVE_MINUTE": "5m",
            "FIFTEEN_MINUTE": "15m",
            "ONE_HOUR": "1h",
            "ONE_DAY": "1d",
        }
        mds_interval = interval_map.get(self.interval, self.interval.lower().replace("_", ""))
        
        # 1. Try Redis for the exact interval (built from real-time WebSocket ticks)
        redis_candle = get_latest_candle(self.symbol, mds_interval)
        if redis_candle:
            return redis_candle
        
        # 2. Try Redis 1m interval (most frequent, may be available sooner)
        redis_candle_1m = get_latest_candle(self.symbol, "1m")
        if redis_candle_1m:
            return redis_candle_1m
        
        return None
    
    async def _fetch_ltp(self) -> Optional[Dict[str, Any]]:
        """Fetch the real-time LTP from Redis ONLY. No REST fallback."""
        return get_latest_tick(self.symbol)
    
    async def _run_tick(self):
        """Execute one tick of the live deployment."""
        if self.status != "running":
            return
        
        candle_data = await self._fetch_live_candle()
        if not candle_data:
            self._log_event("error", f"Failed to fetch candle for {self.symbol}")
            return
        
        # Fetch real-time LTP for accurate live price display
        ltp_data = await self._fetch_ltp()
        if ltp_data and ltp_data.get("ltp", 0) > 0:
            self.current_prices[self.symbol] = ltp_data["ltp"]
        else:
            self.current_prices[self.symbol] = float(candle_data["close"])
        
        ts = str(candle_data["time"])
        ltp_value = self.current_prices[self.symbol]
        
        # Build candle object
        candle = Candle(
            time=ts,
            open=float(candle_data["open"]),
            high=float(candle_data["high"]),
            low=float(candle_data["low"]),
            close=float(candle_data["close"]),
            volume=int(candle_data.get("volume", 0)),
            open_interest=int(candle_data.get("open_interest", 0)),
        )
        self.historical_candles.append(candle)
        if len(self.historical_candles) > 2000:
            self.historical_candles = self.historical_candles[-2000:]
        
        current_candles = {self.symbol: candle_data}
        
        # Phase 1: Match pending orders
        filled_trades, match_rtrades = self.order_mgr.match_pending_orders(
            current_candles=current_candles,
            timestamp=ts,
            current_positions=self.portfolio_mgr.portfolio.positions,
        )
        for trade in filled_trades:
            self.portfolio_mgr.apply_trade(trade)
            self._save_trade(trade)
            self.own_trades.append(RTrade(
                symbol=trade.symbol,
                price=trade.price,
                quantity=trade.qty,
                timestamp=ts,
                direction=trade.direction,
                trade_id=trade.id,
            ))
        
        self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
            self.portfolio_mgr.portfolio.positions
        )
        
        # Phase 2: Mark to market (use LTP if available for more accurate PnL)
        self.portfolio_mgr.mark_to_market(self.current_prices)
        
        # Phase 3: Margin call / liquidation
        if self.portfolio_mgr.is_margin_call():
            liq_trades = self.portfolio_mgr.liquidate_all(
                current_prices=self.current_prices,
                timestamp=ts,
                execution_sim=self.execution_sim,
            )
            for trade in liq_trades:
                self._save_trade(trade)
                self._log_event("margin_call", f"Liquidated {trade.symbol}", {"trade": trade.id})
        
        # Phase 4: Build state and execute strategy
        order_depth = self.order_book_adapter.candle_to_order_depth(self.symbol, pd.Series(candle_data))
        positions_for_state = PortfolioStateBuilder.convert_backtest_positions(
            self.portfolio_mgr.portfolio.positions,
            self.current_prices
        )
        
        trading_state = PortfolioStateBuilder.build_trading_state(
            timestamp=ts,
            order_depths={self.symbol: order_depth},
            own_trades={self.symbol: self.own_trades[-100:]},
            market_trades={self.symbol: []},
            positions=positions_for_state,
            portfolio_equity=self.portfolio_mgr.portfolio.equity,
            portfolio_cash=self.portfolio_mgr.portfolio.cash,
            trader_data=self.trader_data_json,
        )
        
        submitted_orders = []
        if self.portfolio_mgr.portfolio.equity > 0:
            if isinstance(self.runtime, LegacyRuntime):
                market_state = MarketState(
                    current_time=ts,
                    current_candle={self.symbol: candle},
                    historical_candles={self.symbol: list(self.historical_candles)},
                    positions=self.portfolio_mgr.portfolio.positions,
                    portfolio=self.portfolio_mgr.portfolio,
                    active_orders=self.order_mgr.active_orders,
                )
                submitted_orders, self.trader_data_json = self.runtime.on_tick(market_state)
            else:
                submitted_orders, self.trader_data_json = self.runtime.on_tick(trading_state)
        
        strategy_logs = self.runtime.get_logs()
        
        # Phase 5: Process new orders
        new_orders, new_filled, new_rtrades = self.order_mgr.process_submitted_orders(
            submitted_orders=submitted_orders,
            current_candles=current_candles,
            timestamp=ts,
            current_positions=self.portfolio_mgr.portfolio.positions,
        )
        for trade in new_filled:
            self.portfolio_mgr.apply_trade(trade)
            self._save_trade(trade)
            self.own_trades.append(RTrade(
                symbol=trade.symbol,
                price=trade.price,
                quantity=trade.qty,
                timestamp=ts,
                direction=trade.direction,
                trade_id=trade.id,
            ))
        
        # Final mark to market
        self.portfolio_mgr.mark_to_market(self.current_prices)
        self.portfolio_mgr.portfolio.positions = self.order_mgr.prune_zero_positions(
            self.portfolio_mgr.portfolio.positions
        )
        
        # Save PnL snapshot every tick (throttle in production if needed)
        self._save_pnl_snapshot()
        
        # Build notification payload
        snapshot = self.portfolio_mgr.get_snapshot()
        orders_submitted_dicts = [
            {"symbol": o.symbol, "direction": o.direction, "price": o.price, "quantity": o.qty}
            for o in new_orders
        ]
        orders_filled_dicts = [
            {"symbol": t.symbol, "direction": t.direction, "price": t.price,
             "qty": t.qty, "timestamp": t.timestamp, "charges": t.total_charges}
            for t in filled_trades + new_filled
        ]
        
        self._notify("tick", {
            "step": self.step,
            "timestamp": ts,
            "candle": {self.symbol: candle_data},
            "ltp": ltp_value,
            "orders_submitted": orders_submitted_dicts,
            "orders_filled": orders_filled_dicts,
            "portfolio": snapshot,
            "strategy_logs": strategy_logs,
        })
        
        # Log any fills as events
        for trade in filled_trades + new_filled:
            self._log_event("fill", f"{trade.direction} {trade.qty} {trade.symbol} @ {trade.price}", {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "price": trade.price,
                "qty": trade.qty,
                "charges": trade.total_charges,
            })
        
        self.step += 1
    
    async def _loop(self):
        """Main polling loop."""
        self._log_event("start", f"Mock deployment started for {self.symbol} ({self.interval})")
        
        # Subscribe to Market Data Service for real-time ticks
        await self._subscribe_to_market_data()
        
        while not self._stop_event.is_set():
            try:
                if self.status == "running":
                    await self._run_tick()
            except Exception as e:
                print(f"[DeploymentRunner] Tick error: {e}")
                self._log_event("error", f"Tick error: {str(e)}")
            
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue loop
        
        self._log_event("stop", f"Mock deployment stopped for {self.symbol}")
    
    def start(self):
        """Start the deployment runner as an asyncio task."""
        if self.task is None or self.task.done():
            self.status = "running"
            self._stop_event.clear()
            self.task = asyncio.create_task(self._loop())
    
    def pause(self):
        """Pause the deployment (keep task alive but skip ticks)."""
        self.status = "paused"
        self._log_event("pause", "Deployment paused")
    
    def resume(self):
        """Resume a paused deployment."""
        self.status = "running"
        self._log_event("resume", "Deployment resumed")
    
    def stop(self):
        """Stop the deployment runner completely."""
        self.status = "stopped"
        self._stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current deployment status."""
        snapshot = self.portfolio_mgr.get_snapshot()
        
        # Check if we have real-time tick data from Market Data Service
        from backend.services.redis_client import get_latest_tick
        redis_tick = get_latest_tick(self.symbol)
        mds_active = redis_tick is not None
        
        return {
            "deployment_id": self.deployment_id,
            "status": self.status,
            "symbol": self.symbol,
            "interval": self.interval,
            "step": self.step,
            "initial_capital": self.initial_capital,
            "current_price": self.current_prices.get(self.symbol),
            "portfolio": snapshot,
            "active_orders": [
                {"symbol": o.symbol, "direction": o.direction, "type": o.type,
                 "price": o.price, "qty": o.qty, "status": o.status}
                for o in self.order_mgr.active_orders
            ],
            "poll_interval": self.poll_interval_seconds,
            "smartapi_connected": self.smartapi_client is not None and self.smartapi_client.jwt_token is not None,
            "market_data_active": mds_active,
            "mds_subscribed": self._mds_subscribed,
        }


class MockDeploymentEngine:
    """
    Central engine managing all active mock deployments.
    
    Singleton pattern: only one engine instance exists in the app.
    """
    
    _instance: Optional['MockDeploymentEngine'] = None
    
    def __init__(self):
        self.runners: Dict[str, DeploymentRunner] = {}
        self._lock = asyncio.Lock()
    
    @classmethod
    def get_instance(cls) -> 'MockDeploymentEngine':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def start_deployment(
        self,
        deployment_id: str,
        db: Session,
        slippage_pct: float = 0.0,
        use_real_charges: bool = True,
    ) -> Dict[str, Any]:
        """Start a mock deployment runner for a given deployment ID."""
        async with self._lock:
            if deployment_id in self.runners and self.runners[deployment_id].status != "stopped":
                return {"status": "already_running", "deployment_id": deployment_id}
            
            # Load deployment and strategy
            deployment = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
            if not deployment:
                return {"status": "error", "message": "Deployment not found"}
            
            strategy = db.query(StrategyDB).filter(StrategyDB.id == deployment.strategy_id).first()
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
            
            # Determine symbol and interval
            symbols = json.loads(strategy.symbols) if strategy.symbols else ["SBIN"]
            symbol = deployment.symbol or symbols[0]
            interval = strategy.interval or "FIVE_MINUTE"
            initial_capital = strategy.initial_capital or 100000.0
            max_position_size = strategy.max_position_size
            
            # Update deployment status
            deployment.status = "active"
            db.commit()
            
            # Create runner
            runner = DeploymentRunner(
                deployment_id=deployment_id,
                strategy=strategy,
                symbol=symbol,
                interval=interval,
                initial_capital=initial_capital,
                max_position_size=max_position_size,
                slippage_pct=slippage_pct,
                trade_type="INTRADAY",
                use_real_charges=use_real_charges,
            )
            
            self.runners[deployment_id] = runner
            runner.start()
            
            return {
                "status": "started",
                "deployment_id": deployment_id,
                "symbol": symbol,
                "interval": interval,
                "initial_capital": initial_capital,
                "message": "MOCK DEPLOYMENT STARTED — NO REAL MONEY IS BEING USED. All trades are simulated.",
            }
    
    async def stop_deployment(self, deployment_id: str, db: Session) -> Dict[str, Any]:
        """Stop a running mock deployment."""
        async with self._lock:
            runner = self.runners.get(deployment_id)
            if not runner:
                return {"status": "not_found", "deployment_id": deployment_id}
            
            runner.stop()
            
            # Update deployment status
            deployment = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
            if deployment:
                deployment.status = "stopped"
                db.commit()
            
            del self.runners[deployment_id]
            
            return {
                "status": "stopped",
                "deployment_id": deployment_id,
                "message": "Mock deployment stopped. No real orders were placed.",
            }
    
    async def pause_deployment(self, deployment_id: str) -> Dict[str, Any]:
        async with self._lock:
            runner = self.runners.get(deployment_id)
            if not runner:
                return {"status": "not_found"}
            runner.pause()
            return {"status": "paused", "deployment_id": deployment_id}
    
    async def resume_deployment(self, deployment_id: str) -> Dict[str, Any]:
        async with self._lock:
            runner = self.runners.get(deployment_id)
            if not runner:
                return {"status": "not_found"}
            runner.resume()
            return {"status": "resumed", "deployment_id": deployment_id}
    
    def get_runner_status(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        runner = self.runners.get(deployment_id)
        if not runner:
            return None
        return runner.get_status()
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        return [runner.get_status() for runner in self.runners.values()]
    
    def add_sse_callback(self, deployment_id: str, callback: Callable[[str, Dict[str, Any]], None]):
        runner = self.runners.get(deployment_id)
        if runner:
            runner.add_callback(callback)
    
    def remove_sse_callback(self, deployment_id: str, callback: Callable[[str, Dict[str, Any]], None]):
        runner = self.runners.get(deployment_id)
        if runner:
            runner.remove_callback(callback)
