"""
DeploymentOrchestrator: Lightweight orchestrator replacing the monolithic DeploymentRunner.

Sole responsibility: coordinate the workflow by delegating to dedicated services:
  1. MarketFeed — get market data (ticks, candles)
  2. SharedCacheService — store/retrieve historical candles
  3. StrategyExecutor — convert market state to trading decisions
  4. ExecutionEngine — process orders, match fills, apply trades to portfolio
  5. PnLSnapshotScheduler — decide when to take PnL snapshots
  6. PersistenceService — enqueue DB writes asynchronously
  7. EventBus — publish events for SSE and other consumers

No direct DB calls. No direct Redis calls. No WebSocket handling.
"""

import time
import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from engine.datamodels import Candle
from engine.execution import ExecutionSimulator
from engine.portfolio import PortfolioManager
from engine.execution_engine import ExecutionEngine, TradeEvent, OrderEvent
from engine.strategy_executor import StrategyExecutor
from backend.services.market_feed import MarketFeed, create_market_feed
from backend.services.shared_cache import SharedCacheService, get_shared_cache
from backend.services.event_bus import EventBus, Event, EventType, ensure_event_bus
from backend.services.persistence_service import PersistenceService, ensure_persistence_service
from backend.services.pnl_snapshot_scheduler import PnLSnapshotScheduler, PnLSnapshotConfig
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.data_service import normalize_symbol
from backend.database import StrategyDB


class DeploymentOrchestrator:
    """
    Lightweight orchestrator for a single deployment.
    
    Delegates all specialized work to dedicated services.
    """
    
    def __init__(
        self,
        deployment_id: str,
        strategy: StrategyDB,
        symbol: str,
        interval: str,
        initial_capital: float,
        max_position_size: Optional[int] = None,
        slippage_pct: float = 0.0,
        trade_type: str = "INTRADAY",
        use_real_charges: bool = True,
        poll_interval_seconds: Optional[int] = None,
        pnl_snapshot_interval_seconds: float = 30.0,
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
        if poll_interval_seconds is None:
            interval_map = {
                "ONE_MINUTE": 5,
                "FIVE_MINUTE": 10,
                "FIFTEEN_MINUTE": 15,
                "ONE_HOUR": 30,
                "ONE_DAY": 60,
            }
            poll_interval_seconds = interval_map.get(interval, 10)
        self.poll_interval_seconds = poll_interval_seconds
        self.pnl_snapshot_interval_seconds = pnl_snapshot_interval_seconds
        
        # Services (initialized in start())
        self.market_feed: Optional[MarketFeed] = None
        self.shared_cache: Optional[SharedCacheService] = None
        self.event_bus: Optional[EventBus] = None
        self.persistence: Optional[PersistenceService] = None
        self.strategy_executor: Optional[StrategyExecutor] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.pnl_scheduler: Optional[PnLSnapshotScheduler] = None
        
        # Runtime state
        self.status = "stopped"  # running, paused, stopped
        self.task: Optional[asyncio.Task] = None
        self.step = 0
        self.current_prices: Dict[str, float] = {}
        self._stop_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize all services for this deployment."""
        # 1. Market Feed
        self.market_feed = await create_market_feed([self.symbol])
        self.market_feed.subscribe_symbol(self.symbol)
        
        # 2. Shared Cache
        self.shared_cache = get_shared_cache()
        
        # 2b. Warm historical cache with today's data from market open (9:15 AM IST)
        await self._warm_historical_cache()
        
        # 3. Event Bus
        self.event_bus = await ensure_event_bus()
        
        # 4. Persistence Service
        self.persistence = await ensure_persistence_service()
        
        # 5. Strategy Executor
        parameters = json.loads(self.strategy.parameters_json) if self.strategy.parameters_json else None
        self.strategy_executor = StrategyExecutor(
            strategy_code=self.strategy.code or "",
            runtime_type=getattr(self.strategy, 'runtime_type', 'legacy_on_bar'),
            parameters=parameters,
        )
        
        # 6. Execution Engine (wraps PortfolioManager + OrderManager + ExecutionSimulator)
        # Create ONE shared ExecutionSimulator for charge consistency
        shared_execution_sim = ExecutionSimulator(
            slippage_pct=self.slippage_pct,
            default_trade_type=self.trade_type,
        )
        portfolio_mgr = PortfolioManager(
            initial_capital=self.initial_capital,
            default_trade_type=self.trade_type,
            execution_sim=shared_execution_sim,
        )
        self.execution_engine = ExecutionEngine(
            portfolio_mgr=portfolio_mgr,
            execution_sim=shared_execution_sim,
            max_position_size=self.max_position_size,
            slippage_pct=self.slippage_pct,
            trade_type=self.trade_type,
        )
        
        # 7. PnL Snapshot Scheduler
        self.pnl_scheduler = PnLSnapshotScheduler(
            portfolio_mgr=portfolio_mgr,
            config=PnLSnapshotConfig(
                interval_seconds=self.pnl_snapshot_interval_seconds,
                on_trade_fill=True,
                on_margin_call=True,
                pnl_change_threshold_pct=0.5,
            ),
        )
    
    async def _warm_historical_cache(self):
        """Pre-download today's historical candles from market open (9:15 AM IST) up to the last COMPLETED interval."""
        if not SmartAPIManager.is_connected():
            print(f"[DeploymentOrchestrator] SmartAPI not connected. Skipping historical warm-up.")
            return
        
        try:
            from backend.services.data_aggregator import aggregate_data
            from backend.services.data_service import normalize_symbol
            import pytz
            import pandas as pd
            
            client = SmartAPIManager.get_client()
            if not client:
                return
            
            # Resolve symbol to canonical form for SmartAPI
            normalized_symbol = normalize_symbol(self.symbol, self.interval, client)
            
            # Market opens at 9:15 AM IST
            kolkata = pytz.timezone('Asia/Kolkata')
            now = datetime.now(kolkata)
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            
            # If market hasn't opened yet, skip
            if now < market_open:
                print(f"[DeploymentOrchestrator] Market not open yet. Skipping warm-up.")
                return
            
            # Round down to the last completed interval so we don't overlap
            # with the candle the MDS is currently forming
            interval_map = {
                "ONE_MINUTE": 1,
                "FIVE_MINUTE": 5,
                "FIFTEEN_MINUTE": 15,
                "THIRTY_MINUTE": 30,
                "ONE_HOUR": 60,
                "ONE_DAY": 375,
            }
            interval_min = interval_map.get(self.interval.upper(), 1)
            
            # Round down to the last completed minute boundary
            completed_minute = (now.minute // interval_min) * interval_min
            completed_time = now.replace(minute=completed_minute, second=0, microsecond=0)
            
            # If the completed time is before market open, skip (e.g. market just opened)
            if completed_time < market_open:
                print(f"[DeploymentOrchestrator] Not enough history yet. Skipping warm-up.")
                return
            
            start_date = market_open.strftime("%Y-%m-%d %H:%M")
            end_date = completed_time.strftime("%Y-%m-%d %H:%M")
            
            print(f"[DeploymentOrchestrator] Warming cache for {normalized_symbol} from {start_date} to {end_date} ({self.interval})")
            
            df, status = aggregate_data(
                symbol=normalized_symbol,
                interval=self.interval,
                start_date=start_date,
                end_date=end_date,
                client=client,
            )
            
            if df is None or df.empty:
                print(f"[DeploymentOrchestrator] No historical data available for warm-up.")
                return
            
            if status == "mock":
                print(f"[DeploymentOrchestrator] Mock data returned. Skipping warm-up.")
                return
            
            # Clear existing stale data for this symbol+interval to avoid duplicates
            await self.shared_cache.clear_interval(self.symbol, self.interval)
            
            # Convert to shared cache format (time as Unix seconds)
            candles = []
            for _, row in df.iterrows():
                ts_dt = pd.to_datetime(row["time"])
                ts_seconds = int(ts_dt.timestamp())
                candles.append({
                    "time": ts_seconds,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": int(row.get("volume", 0)) if pd.notna(row.get("volume")) else 0,
                    "open_interest": int(row.get("open_interest", 0)) if pd.notna(row.get("open_interest")) else 0,
                })
            
            await self.shared_cache.warm_cache(self.symbol, self.interval, candles)
            print(f"[DeploymentOrchestrator] Warmed cache with {len(candles)} candles for {self.symbol} {self.interval}")
            
        except Exception as e:
            print(f"[DeploymentOrchestrator] Historical warm-up failed: {e}")
    
    async def _run_tick(self):
        """Execute one tick of the deployment workflow."""
        if self.status != "running":
            return
        
        # ---- PHASE 1: Fetch Market Data ----
        candle_data = await self._fetch_live_candle()
        if not candle_data:
            msg = f"No live market data for {self.symbol}. Tick skipped. Ensure market is open and SmartAPI is connected."
            self._publish_event(EventType.DEPLOYMENT_ERROR, {"message": msg})
            self._enqueue_event("error", msg)
            return
        
        # Fetch LTP
        ltp = self.market_feed.get_ltp(self.symbol) if self.market_feed else None
        if ltp and ltp > 0:
            self.current_prices[self.symbol] = ltp
        else:
            self.current_prices[self.symbol] = float(candle_data["close"])
        ltp_value = self.current_prices[self.symbol]
        
        # Format timestamp
        ts = str(candle_data["time"])
        try:
            import pandas as pd
            t_dt = pd.to_datetime(ts, utc=True)
            ts_seconds = int(t_dt.timestamp())
        except Exception:
            ts_seconds = int(time.time())
        
        # Build Candle object
        candle = Candle(
            time=str(ts_seconds),
            open=float(candle_data["open"]),
            high=float(candle_data["high"]),
            low=float(candle_data["low"]),
            close=float(candle_data["close"]),
            volume=int(candle_data.get("volume", 0)),
            open_interest=int(candle_data.get("open_interest", 0)),
        )
        
        # Store formatted candle in shared cache (with integer time for frontend)
        candle_data_formatted = {**candle_data, "time": ts_seconds}
        await self.shared_cache.append_candle(self.symbol, self.interval, candle_data_formatted)
        
        # Get historical candles from shared cache
        historical_candles = []
        cached = await self.shared_cache.get_candles(self.symbol, self.interval)
        if cached:
            for c in cached:
                try:
                    historical_candles.append(Candle(
                        time=str(c.get("time", "")),
                        open=float(c.get("open", 0)),
                        high=float(c.get("high", 0)),
                        low=float(c.get("low", 0)),
                        close=float(c.get("close", 0)),
                        volume=int(c.get("volume", 0)),
                        open_interest=int(c.get("open_interest", 0)),
                    ))
                except Exception:
                    pass
        
        # ---- PHASE 2: Match Pending Orders ----
        current_candles = {self.symbol: candle_data_formatted}
        
        filled_events, _ = self.execution_engine.match_pending_orders(
            current_candles=current_candles,
            timestamp=str(ts_seconds),
        )
        for event in filled_events:
            self._handle_trade_event(event, ts_seconds, "pending_fill")
        
        # ---- PHASE 3: Mark to Market + Margin Check ----
        self.execution_engine.mark_to_market(self.current_prices)
        
        # Check margin call
        liq_events = self.execution_engine.check_margin_and_liquidate(
            current_prices=self.current_prices,
            timestamp=str(ts_seconds),
        )
        for event in liq_events:
            self._handle_trade_event(event, ts_seconds, "margin_call")
            
        # Check dynamic risk limits
        self._check_risk_limits(ts_seconds)
        
        # ---- PHASE 4: Execute Strategy ----
        submitted_orders, trader_data, strategy_logs = self.strategy_executor.execute(
            timestamp=str(ts_seconds),
            candle=candle,
            candle_data=candle_data_formatted,
            historical_candles=historical_candles,
            current_prices=self.current_prices,
            portfolio_positions=self.execution_engine.portfolio_mgr.portfolio.positions,
            portfolio_equity=self.execution_engine.portfolio_mgr.portfolio.equity,
            portfolio_cash=self.execution_engine.portfolio_mgr.portfolio.cash,
            active_orders=self.execution_engine.get_active_orders(),
            portfolio=self.execution_engine.portfolio_mgr.portfolio,
        )
        
        # ---- PHASE 5: Process New Orders ----
        order_events, trade_events, _ = self.execution_engine.process_new_orders(
            submitted_orders=submitted_orders,
            current_candles=current_candles,
            timestamp=str(ts_seconds),
        )
        for event in order_events:
            self._publish_event(EventType.ORDER_SUBMITTED, {
                "order_id": event.order_id,
                "symbol": event.symbol,
                "direction": event.direction,
                "type": event.order_type,
                "price": event.price,
                "qty": event.qty,
                "status": event.status,
            })
        for event in trade_events:
            self._handle_trade_event(event, ts_seconds, "new_fill")
        
        # Final mark to market
        self.execution_engine.mark_to_market(self.current_prices)
        
        # ---- PHASE 6: PnL Snapshot (if scheduled) ----
        event_type = "margin_call" if liq_events else ("trade_fill" if (filled_events or trade_events) else "tick")
        if self.pnl_scheduler.should_snapshot(event_type=event_type):
            snapshot = self.pnl_scheduler.build_snapshot()
            self._enqueue_pnl_snapshot(snapshot)
            self.pnl_scheduler.record_snapshot_taken()
            self._publish_event(EventType.PNL_SNAPSHOT, snapshot)
        
        # ---- PHASE 7: Publish Tick Event ----
        snapshot = self.execution_engine.get_portfolio_snapshot()
        orders_filled_dicts = [
            {"symbol": e.symbol, "direction": e.direction, "price": e.price,
             "qty": e.qty, "timestamp": e.timestamp, "charges": e.total_charges}
            for e in filled_events + trade_events
        ]
        orders_submitted_dicts = [
            {"symbol": e.symbol, "direction": e.direction, "price": e.price, "quantity": e.qty}
            for e in order_events
        ]
        
        self._publish_event(EventType.MARKET_CANDLE, {
            "step": self.step,
            "timestamp": ts_seconds,
            "candle": {self.symbol: candle_data_formatted},
            "ltp": ltp_value,
            "orders_submitted": orders_submitted_dicts,
            "orders_filled": orders_filled_dicts,
            "portfolio": snapshot,
            "strategy_logs": strategy_logs,
        })
        
        self.step += 1
    
    async def _fetch_live_candle(self) -> Optional[Dict[str, Any]]:
        """Fetch latest candle from MarketFeed (Redis only)."""
        if not self.market_feed:
            return None
        
        interval_map = {
            "ONE_MINUTE": "1m",
            "FIVE_MINUTE": "5m",
            "FIFTEEN_MINUTE": "15m",
            "ONE_HOUR": "1h",
            "ONE_DAY": "1d",
        }
        mds_interval = interval_map.get(self.interval, self.interval.lower().replace("_", ""))
        
        # Try exact interval first
        candle = self.market_feed.get_latest_candle(self.symbol, mds_interval)
        if candle:
            return candle
        
        # Fallback to 1m
        candle_1m = self.market_feed.get_latest_candle(self.symbol, "1m")
        if candle_1m:
            return candle_1m
        
        return None
    
    def _check_risk_limits(self, ts_seconds: int):
        """Check dynamic risk limits (e.g. daily drawdown limit) and trigger systematic liquidation on breach."""
        if not self.execution_engine or not self.strategy:
            return
        
        risk_settings = {}
        if self.strategy.risk_settings_json:
            try:
                risk_settings = json.loads(self.strategy.risk_settings_json)
            except Exception:
                pass
        
        if not risk_settings:
            return
            
        portfolio = self.execution_engine.portfolio_mgr.portfolio
        
        # 1. Daily Drawdown Limit Check
        # Check if loss exceeds the configured percentage of initial capital
        max_drawdown_pct = risk_settings.get("max_drawdown_pct") or risk_settings.get("max_daily_loss_pct")
        if max_drawdown_pct:
            limit_amount = self.initial_capital * (float(max_drawdown_pct) / 100.0)
            current_loss = self.initial_capital - portfolio.equity
            if current_loss >= limit_amount:
                msg = f"RISK BREACH: Drawdown limit of {max_drawdown_pct}% breached (Loss: Rs. {current_loss:.2f} >= Limit: Rs. {limit_amount:.2f}). Triggering auto-liquidation."
                print(f"[DeploymentOrchestrator] {msg}")
                
                # Publish error / breach events
                self._publish_event(EventType.DEPLOYMENT_ERROR, {"message": msg})
                self._enqueue_event("risk_breach", msg, {"loss": current_loss, "limit": limit_amount})
                
                # Liquidate all positions immediately
                liq_events = self.execution_engine.liquidate_all_positions(
                    current_prices=self.current_prices,
                    timestamp=str(ts_seconds)
                )
                for event in liq_events:
                    self._handle_trade_event(event, ts_seconds, "risk_liquidation")
                
                # Pause deployment to prevent further trading
                self.pause()
    
    def _handle_trade_event(self, event: TradeEvent, ts_seconds: int, fill_reason: str):
        """Process a trade fill event: portfolio, persistence, event bus."""
        # Record trade for strategy state
        from engine.runtime.datamodels import Trade as RTrade
        rtrade = RTrade(
            symbol=event.symbol,
            price=event.price,
            quantity=event.qty,
            timestamp=str(ts_seconds),
            direction=event.direction,
            trade_id=event.trade_id,
        )
        self.strategy_executor.record_own_trade(rtrade)
        
        # Enqueue persistence
        self._enqueue_trade(event, ts_seconds)
        
        # Publish event — use ts_seconds (integer Unix) for consistent chart alignment
        self._publish_event(EventType.TRADE_FILL, {
            "trade_id": event.trade_id,
            "order_id": event.order_id,
            "symbol": event.symbol,
            "direction": event.direction,
            "price": event.price,
            "qty": event.qty,
            "total_charges": event.total_charges,
            "charges_source": event.charges_source,
            "timestamp": str(ts_seconds),
            "fill_reason": fill_reason,
        })
        
        # Log event
        self._enqueue_event("fill", f"{event.direction} {event.qty} {event.symbol} @ {event.price}", {
            "trade_id": event.trade_id,
            "symbol": event.symbol,
            "direction": event.direction,
            "price": event.price,
            "qty": event.qty,
            "charges": event.total_charges,
        })
        
        # Margin call logging
        if fill_reason == "margin_call":
            self._enqueue_event("margin_call", f"Liquidated {event.symbol}", {"trade_id": event.trade_id})
    
    def _enqueue_trade(self, event: TradeEvent, ts_seconds: Optional[int] = None):
        """Enqueue a trade for async persistence."""
        if self.persistence:
            self.persistence.enqueue_trade(
                deployment_id=self.deployment_id,
                strategy_id=self.strategy.id,
                trade_data={
                    "symbol": event.symbol,
                    "direction": event.direction,
                    "price": event.price,
                    "qty": event.qty,
                    "value": event.value,
                    "brokerage": event.brokerage,
                    "stt": event.stt,
                    "exc_charges": event.exc_charges,
                    "gst": event.gst,
                    "sebi_charges": event.sebi_charges,
                    "stamp_duty": event.stamp_duty,
                    "total_charges": event.total_charges,
                    "charges_source": event.charges_source,
                }
            )
    
    def _enqueue_pnl_snapshot(self, snapshot: Dict[str, Any]):
        """Enqueue a PnL snapshot for async persistence."""
        if self.persistence:
            self.persistence.enqueue_pnl_snapshot(
                deployment_id=self.deployment_id,
                strategy_id=self.strategy.id,
                snapshot_data=snapshot,
            )
    
    def _enqueue_event(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Enqueue a deployment event for async persistence."""
        if self.persistence:
            self.persistence.enqueue_event(
                deployment_id=self.deployment_id,
                event_type=event_type,
                message=message,
                data=data,
            )
    
    def _publish_event(self, event_type: str, payload: Dict[str, Any]):
        """Publish an event to the EventBus."""
        if self.event_bus:
            self.event_bus.publish_sync(
                event_type=event_type,
                source="DeploymentOrchestrator",
                deployment_id=self.deployment_id,
                payload=payload,
            )
    
    async def _loop(self):
        """Main polling loop."""
        self._enqueue_event("start", f"Deployment started for {self.symbol} ({self.interval})")
        self._publish_event(EventType.DEPLOYMENT_START, {"symbol": self.symbol, "interval": self.interval})
        
        while not self._stop_event.is_set():
            try:
                if self.status == "running":
                    await self._run_tick()
            except Exception as e:
                print(f"[DeploymentOrchestrator] Tick error: {e}")
                self._enqueue_event("error", f"Tick error: {str(e)}")
                self._publish_event(EventType.DEPLOYMENT_ERROR, {"message": str(e)})
            
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                pass
        
        self._enqueue_event("stop", f"Deployment stopped for {self.symbol}")
        self._publish_event(EventType.DEPLOYMENT_STOP, {"symbol": self.symbol})
    
    async def start(self):
        """Start the deployment orchestrator."""
        if self.status in ("running", "paused"):
            return
        
        await self.initialize()
        self.status = "running"
        self._stop_event.clear()
        self.task = asyncio.create_task(self._loop())
    
    def pause(self):
        """Pause the deployment."""
        self.status = "paused"
        self._enqueue_event("pause", "Deployment paused")
        self._publish_event(EventType.DEPLOYMENT_PAUSE, {})
    
    def resume(self):
        """Resume a paused deployment."""
        self.status = "running"
        self._enqueue_event("resume", "Deployment resumed")
        self._publish_event(EventType.DEPLOYMENT_RESUME, {})
    
    def stop(self):
        """Stop the deployment completely."""
        self.status = "stopped"
        # Enqueue stop event BEFORE cancelling the task, so it persists even if the loop is interrupted
        self._enqueue_event("stop", f"Deployment stopped for {self.symbol}")
        self._publish_event(EventType.DEPLOYMENT_STOP, {"symbol": self.symbol})
        self._stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current deployment status. Always returns a valid portfolio snapshot."""
        # Safe default portfolio (used when engine isn't ready yet)
        default_portfolio = {
            "cash": self.initial_capital,
            "margin_used": 0.0,
            "margin_free": self.initial_capital,
            "equity": self.initial_capital,
            "unrealized_pnl": 0.0,
            "total_fees": 0.0,
            "total_pnl": 0.0,
            "positions": {},
        }
        
        snapshot = default_portfolio
        if self.execution_engine:
            try:
                snap = self.execution_engine.get_portfolio_snapshot()
                if snap and isinstance(snap, dict) and "equity" in snap:
                    snapshot = snap
            except Exception:
                pass
        
        active_orders = []
        if self.execution_engine:
            try:
                active_orders = [
                    {"symbol": o.symbol, "direction": o.direction, "type": o.type,
                     "price": o.price, "qty": o.qty, "status": o.status}
                    for o in self.execution_engine.get_active_orders()
                ]
            except Exception:
                pass
        
        mds_active = False
        if self.market_feed:
            try:
                tick = self.market_feed.get_latest_tick(self.symbol)
                mds_active = tick is not None
            except Exception:
                pass
        
        return {
            "deployment_id": self.deployment_id,
            "status": self.status,
            "symbol": self.symbol,
            "interval": self.interval,
            "step": self.step,
            "initial_capital": self.initial_capital,
            "current_price": self.current_prices.get(self.symbol),
            "portfolio": snapshot,
            "active_orders": active_orders,
            "poll_interval": self.poll_interval_seconds,
            "smartapi_connected": SmartAPIManager.is_connected(),
            "market_data_active": mds_active,
            "mds_subscribed": self.market_feed is not None,
        }
    
    def place_manual_order(
        self,
        direction: str,
        qty: int,
        price: Optional[float] = None,
        order_type: str = "MARKET"
    ) -> Dict[str, Any]:
        """Place a manual order through the ExecutionEngine."""
        current_price = self.current_prices.get(self.symbol)
        if not current_price:
            latest = self.market_feed.get_latest_candle(self.symbol, "1m") if self.market_feed else None
            if latest:
                current_price = float(latest.get("close", 0))
        if not current_price:
            raise ValueError(f"No current price available for {self.symbol}")
        
        from datetime import datetime
        import pytz
        kolkata = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(kolkata)
        ts_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
        t_naive = now_ist.replace(tzinfo=None)
        t_utc = t_naive.replace(tzinfo=pytz.utc)
        ts_seconds = int(t_utc.timestamp())
        
        smartapi_client = SmartAPIManager.get_client() if SmartAPIManager.is_connected() else None
        
        trade_event = self.execution_engine.execute_manual_order(
            symbol=self.symbol,
            direction=direction,
            qty=qty,
            price=price,
            order_type=order_type,
            current_price=current_price,
            timestamp=ts_str,
            use_real_charges=self.use_real_charges,
            smartapi_client=smartapi_client,
        )
        
        self._handle_trade_event(trade_event, ts_seconds, "manual_order")
        
        # Trigger PnL snapshot check
        if self.pnl_scheduler and self.pnl_scheduler.should_snapshot(event_type="manual_order"):
            snapshot = self.pnl_scheduler.build_snapshot()
            self._enqueue_pnl_snapshot(snapshot)
            self.pnl_scheduler.record_snapshot_taken()
        
        snapshot = self.execution_engine.get_portfolio_snapshot()
        self._publish_event(EventType.MANUAL_ORDER, {
            "trade": {
                "id": trade_event.trade_id,
                "symbol": self.symbol,
                "direction": direction,
                "price": trade_event.price,
                "qty": qty,
                "timestamp": str(ts_seconds),
                "total_charges": trade_event.total_charges,
            },
            "portfolio": snapshot,
        })
        
        return {
            "status": "success",
            "message": f"Manual {direction.upper()} order for {qty} shares filled at Rs. {trade_event.price:.2f}",
            "trade_id": trade_event.trade_id,
            "portfolio": snapshot,
        }
    
    def reset_capital(self, amount: float):
        """Reset portfolio capital."""
        if self.execution_engine and self.execution_engine.portfolio_mgr:
            self.execution_engine.portfolio_mgr.portfolio.cash = amount
            self.execution_engine.portfolio_mgr.portfolio.equity = amount
            self.execution_engine.portfolio_mgr.portfolio.total_fees = 0.0
            self.execution_engine.portfolio_mgr.portfolio.total_pnl = 0.0
            self.execution_engine.portfolio_mgr.portfolio.positions.clear()
        
        if self.pnl_scheduler:
            self.pnl_scheduler.reset()
        
        snapshot = self.execution_engine.get_portfolio_snapshot() if self.execution_engine else {}
        self._enqueue_pnl_snapshot(snapshot)
        self._enqueue_event("reset_capital", f"Reset starting capital to Rs. {amount:.2f}")
        self._publish_event(EventType.PORTFOLIO_UPDATE, snapshot)
        
        return {
            "status": "success",
            "message": f"Starting capital reset to Rs. {amount:.2f}",
            "portfolio": snapshot,
        }
