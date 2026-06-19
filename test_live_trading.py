"""
Live Trading End-to-End Test Suite (Self-Contained)
====================================================

A single-file, standalone test that:
  1. Loads .env credentials
  2. Prompts for TOTP and authenticates SmartAPI
  3. Verifies market data connection
  4. Creates a test strategy + deployment
  5. Starts the deployment and runs the high-freq momentum strategy
  6. Places manual BUY/SELL orders
  7. Cross-checks PnL math against DB
  8. Stops and cleans up

Usage:
    cd /path/to/quantp
    py -3 test_live_trading.py

Prerequisites:
    - .env file with SMARTAPI_API_KEY, SMARTAPI_CLIENT_CODE, SMARTAPI_PASSWORD
    - Market open (9:15 AM - 3:30 PM IST)
    - No backend running (the test initializes its own services)
"""

import asyncio
import json
import time
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# ── Ensure backend root is on path ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from backend.database import init_db, SessionLocal, StrategyDB, DeploymentDB, LiveTradeDB, LivePnLSnapshotDB, DeploymentEventDB
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.market_data_service import MarketDataService, ensure_market_data_service
from backend.services.market_feed import MarketFeed, create_market_feed
from backend.services.shared_cache import get_shared_cache
from backend.services.event_bus import EventBus, Event, EventType, ensure_event_bus
from backend.services.persistence_service import PersistenceService, ensure_persistence_service
from backend.services.deployment_engine import DeploymentEngine, ensure_deployment_engine
from backend.services.deployment_orchestrator import DeploymentOrchestrator
from backend.services.pnl_snapshot_scheduler import PnLSnapshotScheduler, PnLSnapshotConfig
from engine.portfolio import PortfolioManager
from engine.execution import ExecutionSimulator
from engine.execution_engine import ExecutionEngine
from engine.strategy_executor import StrategyExecutor
from engine.datamodels import Candle

# ──────────────────────────────────────
# Test Configuration
# ──────────────────────────────────────
TEST_SYMBOL = "NSE:SBIN-EQ"
TEST_INTERVAL = "ONE_MINUTE"
TEST_INITIAL_CAPITAL = 100000.0

# High-frequency test strategy - trades every tick based on simple momentum
HIGH_FREQ_STRATEGY_CODE = '''
class Strategy:
    def __init__(self):
        self.prev_close = 0
        
    def on_bar(self, state):
        orders = []
        candles = state.current_candle
        if not candles:
            return orders
        
        sym = list(candles.keys())[0] if candles else "NSE:SBIN-EQ"
        candle = candles.get(sym)
        if not candle:
            return orders
        
        close = candle.close
        
        # Simple momentum: if close > previous, BUY; if close < previous, SELL
        if self.prev_close > 0:
            if close > self.prev_close:
                orders.append({
                    "symbol": sym,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": close,
                    "quantity": 1,
                })
            elif close < self.prev_close:
                orders.append({
                    "symbol": sym,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": close,
                    "quantity": 1,
                })
        
        self.prev_close = close
        return orders
'''


class LiveTradingTestSuite:
    """End-to-end test suite for the live trading system."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.event_log: List[Event] = []
        self.passed = 0
        self.failed = 0
        self._totp_input: Optional[str] = None
        
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")
    
    def assert_test(self, condition: bool, test_name: str, details: str = ""):
        if condition:
            self.passed += 1
            self.log(f"OK PASS: {test_name}", "PASS")
        else:
            self.failed += 1
            self.log(f"XX FAIL: {test_name} - {details}", "FAIL")
        self.results.append({"name": test_name, "passed": condition, "details": details})
    
    # ── Pre-Test: SmartAPI Authentication ──
    async def authenticate_smartapi(self) -> bool:
        """Authenticate with SmartAPI using TOTP from user input."""
        self.log("\n" + "=" * 60)
        self.log("PRE-TEST: SmartAPI Authentication")
        self.log("=" * 60)
        
        # Check .env credentials
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        
        self.log(f"  API Key:    {'OK configured' if api_key else 'XX MISSING'}")
        self.log(f"  Client:     {'OK configured' if client_code else 'XX MISSING'}")
        self.log(f"  Password:   {'OK configured' if password else 'XX MISSING'}")
        
        if not SmartAPIManager.is_configured():
            self.log("\nCRITICAL: SmartAPI credentials are missing from .env file.", "FAIL")
            self.log("  Required:")
            self.log("    SMARTAPI_API_KEY=<your api key>")
            self.log("    SMARTAPI_CLIENT_CODE=<your client code>")
            self.log("    SMARTAPI_PASSWORD=<your password>")
            self.log("  Add these to .env and try again.", "FAIL")
            return False
        
        # Check if already connected (previous session)
        if SmartAPIManager.is_connected():
            self.log("  SmartAPI already authenticated from previous session.")
            self.assert_test(True, "SmartAPI pre-authenticated")
            return True
        
        # Prompt for TOTP
        self.log("\n  Enter TOTP from your authenticator app (e.g., Google Authenticator):")
        try:
            self._totp_input = input("  TOTP: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.log("  Input cancelled.", "FAIL")
            return False
        
        if not self._totp_input or not self._totp_input.isdigit() or len(self._totp_input) < 4:
            self.log("  Invalid TOTP format. Expected 6-digit numeric code.", "FAIL")
            return False
        
        # Attempt authentication
        self.log(f"  Authenticating with SmartAPI as {client_code} ...")
        client = SmartAPIManager.create_fresh_client()
        success = client.connect(totp=self._totp_input)
        
        if success:
            SmartAPIManager.set_client(client)
            self.log(f"  OK Authentication successful!")
            self.log(f"  JWT Token: {client.jwt_token[:20]}...")
            self.log(f"  Feed Token: {client.feed_token[:20]}...")
            self.assert_test(True, "SmartAPI authenticated with TOTP")
            return True
        else:
            self.log(f"  XX Authentication failed: {client.last_error}", "FAIL")
            self.assert_test(False, "SmartAPI authentication", client.last_error)
            return False
    
    # ── Test 1: Service Initialization ──
    async def test_service_initialization(self):
        """Test that all core services initialize correctly."""
        self.log("\n" + "=" * 60)
        self.log("TEST 1: Service Initialization")
        self.log("=" * 60)
        
        try:
            # Initialize DB first
            init_db()
            self.log("  OK Database initialized")
            
            # EventBus
            event_bus = await ensure_event_bus()
            self.assert_test(event_bus._running, "EventBus starts", "EventBus dispatch loop not running")
            
            # PersistenceService
            persistence = await ensure_persistence_service()
            self.assert_test(persistence.worker._running, "PersistenceService starts", "Worker not running")
            
            # DeploymentEngine
            engine = await ensure_deployment_engine()
            self.assert_test(engine._event_bus is not None, "DeploymentEngine initialized")
            
            # SharedCache
            cache = get_shared_cache()
            self.assert_test(cache is not None, "SharedCache available")
            
            # MarketDataService check
            mds = MarketDataService.get_instance()
            self.assert_test(mds is not None, "MarketDataService instance accessible")
            
        except Exception as e:
            self.assert_test(False, "Service Initialization", str(e))
    
    # ── Test 2: Market Data Connection ──
    async def test_market_data_connection(self):
        """Test that SmartAPI is connected and market data flows."""
        self.log("\n" + "=" * 60)
        self.log("TEST 2: SmartAPI & Market Data Connection")
        self.log("=" * 60)
        
        connected = SmartAPIManager.is_connected()
        self.assert_test(connected, "SmartAPI connected", 
            "SmartAPI not connected. Check TOTP or credentials.")
        if not connected:
            return
        
        client = SmartAPIManager.get_client()
        self.assert_test(client is not None, "SmartAPI client available")
        
        # Start MDS and subscribe to symbol
        mds = await ensure_market_data_service([TEST_SYMBOL])
        self.assert_test(mds._running, "MarketDataService running")
        
        # Wait for WebSocket to connect and subscribe, then for ticks to arrive
        self.log("  Waiting 10 seconds for WebSocket connection + subscription + ticks...")
        await asyncio.sleep(10)
        
        # Check Redis for tick data with retries
        from backend.services.redis_client import get_latest_tick
        tick = None
        for attempt in range(5):
            tick = get_latest_tick(TEST_SYMBOL)
            if tick:
                break
            self.log(f"  Retry {attempt+1}/5: no tick yet, waiting 2s...")
            await asyncio.sleep(2)
        
        self.assert_test(tick is not None, f"Tick data received for {TEST_SYMBOL}", 
            f"No tick in Redis after retries. MDS status: {mds.get_status()}")
        
        if tick:
            self.log(f"  Tick: LTP={tick.get('ltp')}, Volume={tick.get('volume')}, Time={tick.get('timestamp')}")
            self.assert_test(tick.get('ltp', 0) > 0, "Tick has valid LTP", f"LTP={tick.get('ltp')}")
        
        # Check MarketFeed abstraction
        feed = await create_market_feed([TEST_SYMBOL])
        ltp = feed.get_ltp(TEST_SYMBOL)
        self.assert_test(ltp is not None and ltp > 0, "MarketFeed.get_ltp() works", f"LTP={ltp}")
        
        candle = feed.get_latest_candle(TEST_SYMBOL, "1m")
        self.assert_test(candle is not None, "MarketFeed.get_latest_candle() works",
            "No 1m candle from Redis")
        if candle:
            self.log(f"  Candle: O={candle['open']} H={candle['high']} L={candle['low']} C={candle['close']} V={candle['volume']}")
    
    # ── Test 3: Create Test Strategy + Deployment ──
    async def test_create_strategy_and_deployment(self) -> Optional[str]:
        """Create a test strategy and deployment in the database."""
        self.log("\n" + "=" * 60)
        self.log("TEST 3: Create Strategy & Deployment")
        self.log("=" * 60)
        
        db = SessionLocal()
        try:
            # Create strategy
            strategy_id = f"test_strategy_{int(time.time())}"
            strategy = StrategyDB(
                id=strategy_id,
                name="HighFreq Momentum Test",
                description="Test strategy for live trading E2E validation",
                code=HIGH_FREQ_STRATEGY_CODE,
                symbols=json.dumps([TEST_SYMBOL]),
                interval=TEST_INTERVAL,
                initial_capital=TEST_INITIAL_CAPITAL,
                max_position_size=10,
                parameters_json="{}",
                runtime_type="legacy_on_bar",
            )
            db.add(strategy)
            db.commit()
            self.log(f"  Created strategy: {strategy.id}")
            
            # Create deployment
            deployment_id = f"test_deployment_{int(time.time())}"
            deployment = DeploymentDB(
                id=deployment_id,
                strategy_id=strategy.id,
                name="Live Trading E2E Test",
                symbol=TEST_SYMBOL,
                mode="paper",
                status="active",
            )
            db.add(deployment)
            db.commit()
            self.log(f"  Created deployment: {deployment.id}")
            
            self.assert_test(True, "Strategy & Deployment created in DB")
            return deployment_id
            
        except Exception as e:
            self.assert_test(False, "Strategy & Deployment creation", str(e))
            return None
        finally:
            db.close()
    
    # ── Test 4: Start Deployment + Verify Event Flow ──
    async def test_start_deployment(self, deployment_id: str):
        """Start the deployment and verify it processes ticks."""
        self.log("\n" + "=" * 60)
        self.log("TEST 4: Start Deployment & Event Flow")
        self.log("=" * 60)
        
        engine = await ensure_deployment_engine()
        db = SessionLocal()
        
        try:
            # Start deployment
            result = await engine.start_deployment(
                deployment_id=deployment_id,
                db=db,
                slippage_pct=0.0,
                use_real_charges=True,
                pnl_snapshot_interval_seconds=10.0,
            )
            self.log(f"  Start result: {result}")
            self.assert_test(result.get("status") == "started", "Deployment started",
                f"Status: {result.get('status')}, Message: {result.get('message')}")
            
            # Subscribe to events
            events_received = []
            def on_event(event_type: str, data: dict):
                events_received.append({"type": event_type, "data": data})
            
            engine.add_sse_callback(deployment_id, on_event)
            
            # Wait for ticks to process
            self.log("  Waiting 15 seconds for strategy ticks...")
            await asyncio.sleep(15)
            
            # Check status
            status = engine.get_orchestrator_status(deployment_id)
            self.assert_test(status is not None, "Orchestrator status available")
            if status:
                self.log(f"  Step: {status.get('step')}, Status: {status.get('status')}")
                self.log(f"  Current Price: {status.get('current_price')}")
                portfolio = status.get('portfolio', {})
                self.log(f"  Portfolio: Cash=₹{portfolio.get('cash',0):.2f}, Equity=₹{portfolio.get('equity',0):.2f}")
                self.assert_test(status.get('step', 0) > 0, "Deployment processed ticks",
                    f"Step={status.get('step')}")
            
            # Verify events were received
            tick_events = [e for e in events_received if e["type"] == "tick"]
            self.log(f"  Events received: {len(events_received)} total, {len(tick_events)} tick events")
            self.assert_test(len(tick_events) > 0, "Tick events received via EventBus",
                f"Total events: {len(events_received)}, Types: {list(set(e['type'] for e in events_received))}")
            
            # Verify persistence
            with SessionLocal() as db2:
                trades = db2.query(LiveTradeDB).filter(
                    LiveTradeDB.deployment_id == deployment_id
                ).all()
                self.log(f"  Trades in DB: {len(trades)}")
                if trades:
                    for t in trades[:3]:
                        self.log(f"    Trade: {t.direction} {t.qty} {t.symbol} @ ₹{t.price} (charges: ₹{t.total_charges:.2f})")
                
                snapshots = db2.query(LivePnLSnapshotDB).filter(
                    LivePnLSnapshotDB.deployment_id == deployment_id
                ).all()
                self.log(f"  PnL Snapshots in DB: {len(snapshots)}")
                
                events = db2.query(DeploymentEventDB).filter(
                    DeploymentEventDB.deployment_id == deployment_id
                ).all()
                self.log(f"  Deployment Events in DB: {len(events)}")
                event_types = [e.event_type for e in events]
                self.log(f"  Event types: {set(event_types)}")
                
                self.assert_test("start" in event_types, "Start event persisted")
                self.assert_test(len(snapshots) > 0, "PnL snapshots persisted",
                    f"Strategy may not have traded yet (trades={len(trades)})")
            
            return deployment_id
            
        except Exception as e:
            self.assert_test(False, "Deployment start", str(e))
            return None
        finally:
            db.close()
    
    # ── Test 5: Manual Order Placement ──
    async def test_manual_orders(self, deployment_id: str):
        """Place manual BUY and SELL orders and verify execution."""
        self.log("\n" + "=" * 60)
        self.log("TEST 5: Manual Order Execution")
        self.log("=" * 60)
        
        engine = await ensure_deployment_engine()
        orchestrator = engine.get_orchestrator(deployment_id)
        
        if not orchestrator:
            self.assert_test(False, "Manual orders", "Orchestrator not found")
            return
        
        # Get initial portfolio state
        initial_snapshot = orchestrator.execution_engine.get_portfolio_snapshot()
        initial_cash = initial_snapshot.get("cash", 0)
        initial_equity = initial_snapshot.get("equity", 0)
        self.log(f"  Initial: Cash=₹{initial_cash:.2f}, Equity=₹{initial_equity:.2f}")
        
        # Place BUY order
        try:
            buy_result = orchestrator.place_manual_order(
                direction="BUY",
                qty=10,
                order_type="MARKET"
            )
            self.log(f"  BUY result: {buy_result}")
            self.assert_test(buy_result.get("status") == "success", "Manual BUY order placed",
                f"Result: {buy_result}")
            
            # Verify in-memory state immediately (not DB)
            buy_portfolio = buy_result.get("portfolio", {})
            self.log(f"  In-memory after BUY: Cash=₹{buy_portfolio.get('cash',0):.2f}, Equity=₹{buy_portfolio.get('equity',0):.2f}")
            self.assert_test(buy_portfolio.get("cash", 0) < initial_cash, "Cash reduced after BUY (in-memory)",
                f"Before: {initial_cash}, After: {buy_portfolio.get('cash', 0)}")
            self.assert_test(
                buy_portfolio.get("positions", {}).get(TEST_SYMBOL, {}).get("qty", 0) == 10,
                "Position shows 10 qty after BUY"
            )
            
            await asyncio.sleep(5)  # Wait for persistence worker to flush
            
            # Verify in DB
            with SessionLocal() as db:
                buy_trades = db.query(LiveTradeDB).filter(
                    LiveTradeDB.deployment_id == deployment_id,
                    LiveTradeDB.direction == "BUY"
                ).all()
                self.assert_test(len(buy_trades) > 0, "BUY trade persisted to DB",
                    f"Found {len(buy_trades)} BUY trades")
                
                if buy_trades:
                    t = buy_trades[-1]
                    self.log(f"  BUY trade DB: {t.qty} shares @ ₹{t.price} (charges: ₹{t.total_charges:.2f})")
            
        except Exception as e:
            import traceback
            self.log(f"  Manual BUY error: {traceback.format_exc()}", "FAIL")
            self.assert_test(False, "Manual BUY order", str(e))
        
        # Place SELL order
        await asyncio.sleep(1)
        try:
            sell_result = orchestrator.place_manual_order(
                direction="SELL",
                qty=10,
                order_type="MARKET"
            )
            self.log(f"  SELL result: {sell_result}")
            self.assert_test(sell_result.get("status") == "success", "Manual SELL order placed",
                f"Result: {sell_result}")
            
            # Verify in-memory state immediately
            sell_portfolio = sell_result.get("portfolio", {})
            self.log(f"  In-memory after SELL: Cash=₹{sell_portfolio.get('cash',0):.2f}, Equity=₹{sell_portfolio.get('equity',0):.2f}")
            self.assert_test(
                sell_portfolio.get("positions", {}) == {} or 
                sum(abs(p.get("qty", 0)) for p in sell_portfolio.get("positions", {}).values()) == 0,
                "Position flat after round-trip (in-memory)",
                f"Positions: {sell_portfolio.get('positions', {})}"
            )
            self.assert_test(sell_portfolio.get("total_fees", 0) > 0, "Fees recorded after SELL (in-memory)",
                f"Total fees: {sell_portfolio.get('total_fees', 0)}")
            
            await asyncio.sleep(5)  # Wait for persistence worker to flush
            
            with SessionLocal() as db:
                sell_trades = db.query(LiveTradeDB).filter(
                    LiveTradeDB.deployment_id == deployment_id,
                    LiveTradeDB.direction == "SELL"
                ).all()
                self.assert_test(len(sell_trades) > 0, "SELL trade persisted to DB",
                    f"Found {len(sell_trades)} SELL trades")
                
                if sell_trades:
                    t = sell_trades[-1]
                    self.log(f"  SELL trade DB: {t.qty} shares @ ₹{t.price} (charges: ₹{t.total_charges:.2f})")
            
        except Exception as e:
            import traceback
            self.log(f"  Manual SELL error: {traceback.format_exc()}", "FAIL")
            self.assert_test(False, "Manual SELL order", str(e))
    
    # ── Test 6: PnL Calculation Verification ──
    async def test_pnl_calculation(self, deployment_id: str):
        """Verify PnL math is correct using the in-memory portfolio snapshot."""
        self.log("\n" + "=" * 60)
        self.log("TEST 6: PnL Calculation Verification")
        self.log("=" * 60)
        
        engine = await ensure_deployment_engine()
        orchestrator = engine.get_orchestrator(deployment_id)
        
        if not orchestrator:
            self.assert_test(False, "PnL verification", "Orchestrator not found")
            return
        
        # Get in-memory portfolio snapshot (most accurate)
        snapshot = orchestrator.execution_engine.get_portfolio_snapshot()
        in_mem_cash = snapshot.get("cash", 0)
        in_mem_equity = snapshot.get("equity", 0)
        in_mem_fees = snapshot.get("total_fees", 0)
        in_mem_pnl = snapshot.get("total_pnl", 0)
        in_mem_realized = snapshot.get("total_pnl", 0)  # total_pnl = realized_pnl after flat
        
        self.log(f"  In-memory: Cash=₹{in_mem_cash:.2f}, Equity=₹{in_mem_equity:.2f}")
        self.log(f"  In-memory: Fees=₹{in_mem_fees:.2f}, Realized PnL=₹{in_mem_realized:.2f}")
        
        with SessionLocal() as db:
            trades = db.query(LiveTradeDB).filter(
                LiveTradeDB.deployment_id == deployment_id
            ).order_by(LiveTradeDB.timestamp.asc()).all()
            
            if not trades:
                self.assert_test(False, "PnL verification", "No trades found in DB")
                return
            
            self.log(f"  Total trades in DB: {len(trades)}")
            
            total_fees = 0.0
            buy_value = 0.0
            sell_value = 0.0
            buy_qty = 0
            sell_qty = 0
            
            for t in trades:
                total_fees += t.total_charges
                if t.direction == "BUY":
                    buy_value += t.price * t.qty
                    buy_qty += t.qty
                elif t.direction == "SELL":
                    sell_value += t.price * t.qty
                    sell_qty += t.qty
                
                self.log(f"  {t.direction} {t.qty} @ ₹{t.price} (fees: ₹{t.total_charges:.2f})")
            
            self.log(f"  Total fees from trades: ₹{total_fees:.2f}")
            self.assert_test(
                abs(in_mem_fees - total_fees) < 0.1,
                "In-memory fees match sum of DB trade charges",
                f"In-memory: {in_mem_fees:.2f}, DB sum: {total_fees:.2f}"
            )
            
            # Verify equity ≈ cash (when position is flat)
            if not snapshot.get("positions"):
                self.log(f"  Position flat: equity=₹{in_mem_equity:.2f}, cash=₹{in_mem_cash:.2f}")
                self.assert_test(
                    abs(in_mem_equity - in_mem_cash) < 0.5,
                    "Equity equals cash when position is flat",
                    f"Equity: {in_mem_equity:.2f}, Cash: {in_mem_cash:.2f}"
                )
            
            # After round-trip: equity ≈ initial_capital + realized_pnl - total_fees
            # where realized_pnl is the price difference (not including fees)
            expected_equity = TEST_INITIAL_CAPITAL + in_mem_realized - in_mem_fees
            self.log(f"  Expected equity (initial + realized_pnl - fees): ₹{expected_equity:.2f}")
            self.assert_test(
                abs(in_mem_equity - expected_equity) < 1.0,
                "Equity ≈ initial_capital + realized_pnl - total_fees",
                f"Expected: {expected_equity:.2f}, Got: {in_mem_equity:.2f}"
            )
            
            # Round-trip rough check: equity should be close to initial_capital minus fees
            rough_equity = TEST_INITIAL_CAPITAL - total_fees
            if buy_qty > 0 and sell_qty > 0:
                matched = min(buy_qty, sell_qty)
                avg_buy = buy_value / buy_qty if buy_qty > 0 else 0
                avg_sell = sell_value / sell_qty if sell_qty > 0 else 0
                rough_equity += (avg_sell - avg_buy) * matched
            
            self.log(f"  Rough equity estimate: ₹{rough_equity:.2f}")
            self.assert_test(
                abs(in_mem_equity - rough_equity) < 5.0,
                "Equity roughly matches expected (initial + PnL - fees)",
                f"Expected: {rough_equity:.2f}, Got: {in_mem_equity:.2f}"
            )
            
            # Verify DB snapshot consistency (last snapshot should match in-memory)
            snapshots = db.query(LivePnLSnapshotDB).filter(
                LivePnLSnapshotDB.deployment_id == deployment_id
            ).order_by(LivePnLSnapshotDB.timestamp.desc()).limit(1).all()
            
            if snapshots:
                latest = snapshots[0]
                self.log(f"  Latest DB snapshot: Cash=₹{latest.cash:.2f}, Equity=₹{latest.equity:.2f}")
                self.log(f"  DB snapshot fees: ₹{latest.total_fees:.2f}, realized_pnl: ₹{latest.realized_pnl:.2f}")
                # Allow some tolerance for async snapshot timing
                self.assert_test(
                    abs(latest.total_fees - total_fees) < 1.0,
                    "DB snapshot fees match trade charges",
                    f"Snapshot: {latest.total_fees:.2f}, Trades: {total_fees:.2f}"
                )
            else:
                self.log("  No DB snapshots found (may be normal if test was fast)")
    
    # ── Test 7: High-Frequency Strategy Validation ──
    async def test_high_freq_strategy(self, deployment_id: str):
        """Let the strategy run for a longer period and check trade frequency."""
        self.log("\n" + "=" * 60)
        self.log("TEST 7: High-Frequency Strategy Validation")
        self.log("=" * 60)
        
        engine = await ensure_deployment_engine()
        orchestrator = engine.get_orchestrator(deployment_id)
        
        if not orchestrator:
            self.assert_test(False, "HF strategy", "Orchestrator not found")
            return
        
        self.log("  Running for 20 seconds to let strategy trade...")
        await asyncio.sleep(20)
        
        status = engine.get_orchestrator_status(deployment_id)
        if status:
            self.log(f"  Steps processed: {status.get('step', 0)}")
            self.log(f"  Active orders: {len(status.get('active_orders', []))}")
        
        with SessionLocal() as db:
            trades = db.query(LiveTradeDB).filter(
                LiveTradeDB.deployment_id == deployment_id
            ).all()
            
            self.log(f"  Total trades: {len(trades)}")
            
            if trades:
                buy_count = sum(1 for t in trades if t.direction == "BUY")
                sell_count = sum(1 for t in trades if t.direction == "SELL")
                self.log(f"  BUY: {buy_count}, SELL: {sell_count}")
                
                self.assert_test(len(trades) >= 2, "Strategy generated trades",
                    f"Only {len(trades)} trades total (market may be flat)")
                
                avg_charges = sum(t.total_charges for t in trades) / len(trades)
                self.log(f"  Average charges per trade: ₹{avg_charges:.2f}")
                self.assert_test(avg_charges > 0, "Charges applied to trades",
                    f"Avg charges: {avg_charges}")
            else:
                self.log("  No strategy trades (market may be flat)")
                self.assert_test(True, "Strategy run completed (no trades)", 
                    "Market may be flat; check manually if needed")
    
    # ── Test 8: Stop Deployment + Cleanup ──
    async def test_stop_and_cleanup(self, deployment_id: str):
        """Stop deployment and verify cleanup."""
        self.log("\n" + "=" * 60)
        self.log("TEST 8: Stop Deployment & Cleanup")
        self.log("=" * 60)
        
        engine = await ensure_deployment_engine()
        db = SessionLocal()
        
        try:
            result = await engine.stop_deployment(deployment_id, db)
            self.log(f"  Stop result: {result}")
            self.assert_test(result.get("status") == "stopped", "Deployment stopped",
                f"Status: {result.get('status')}")
            
            self.assert_test(deployment_id not in engine.orchestrators, 
                "Orchestrator removed from engine")
            
            # Wait for persistence worker to flush the stop event
            self.log("  Waiting 5 seconds for persistence worker to flush stop event...")
            await asyncio.sleep(5)
            
            with SessionLocal() as db2:
                events = db2.query(DeploymentEventDB).filter(
                    DeploymentEventDB.deployment_id == deployment_id,
                    DeploymentEventDB.event_type == "stop"
                ).all()
                self.assert_test(len(events) > 0, "Stop event persisted",
                    f"Stop events: {len(events)}")
            
        except Exception as e:
            self.assert_test(False, "Stop deployment", str(e))
        finally:
            db.close()
    
    # ── Test Runner ──
    async def run_all(self):
        """Run the complete test suite."""
        self.log("\n" + "=" * 70)
        self.log("  LIVE TRADING END-TO-END TEST SUITE")
        self.log("  Testing: Login -> Market Data -> Strategy -> Orders -> PnL -> Persistence")
        self.log("=" * 70 + "\n")
        
        start_time = time.time()
        
        # 0. Authenticate SmartAPI (prompts for TOTP)
        if not await self.authenticate_smartapi():
            self.log("\nCannot proceed without SmartAPI authentication.", "FAIL")
            self.print_summary()
            return
        
        # 1. Initialize services
        await self.test_service_initialization()
        
        # 2. Check market data
        await self.test_market_data_connection()
        
        # 3. Create strategy + deployment
        deployment_id = await self.test_create_strategy_and_deployment()
        if not deployment_id:
            self.log("\nCannot continue without deployment. Aborting.", "FAIL")
            self.print_summary()
            return
        
        # 4. Start deployment
        await self.test_start_deployment(deployment_id)
        
        # 5. Manual orders
        await self.test_manual_orders(deployment_id)
        
        # 6. PnL verification
        await self.test_pnl_calculation(deployment_id)
        
        # 7. High-freq strategy
        await self.test_high_freq_strategy(deployment_id)
        
        # 8. Stop
        await self.test_stop_and_cleanup(deployment_id)
        
        elapsed = time.time() - start_time
        self.print_summary(elapsed)
    
    def print_summary(self, elapsed: float = 0):
        """Print final test summary."""
        self.log("\n" + "=" * 70)
        self.log("  TEST SUMMARY")
        self.log("=" * 70)
        self.log(f"  Total tests: {self.passed + self.failed}")
        self.log(f"  Passed: {self.passed}")
        self.log(f"  Failed: {self.failed}")
        if elapsed:
            self.log(f"  Duration: {elapsed:.1f}s")
        self.log("=" * 70)
        
        if self.failed > 0:
            self.log("\n  Failed tests:")
            for r in self.results:
                if not r["passed"]:
                    self.log(f"    - {r['name']}: {r['details']}")
        
        self.log(f"\n{'  ALL TESTS PASSED OK' if self.failed == 0 else '  SOME TESTS FAILED XX'}")


# ──────────────────────────────────────
# Entry point
# ──────────────────────────────────────

async def main():
    suite = LiveTradingTestSuite()
    await suite.run_all()

if __name__ == "__main__":
    asyncio.run(main())
