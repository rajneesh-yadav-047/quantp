"""
Test runner for GOLDEN CROSSOVER NIFTY SELLING strategy.

Usage:
    python test_golden_crossover_nifty_selling.py

Flow:
1. Loads .env credentials from project root
2. Prompts for SmartAPI TOTP code
3. Authenticates with Angel One SmartAPI
4. Fetches NIFTY 50 spot 3-minute candles (chunked, real data only)
5. Loads the strategy from strategies/golden_crossover_nifty_selling.py
6. Runs backtest via BacktestEngine
7. Prints summary metrics and pricing mode

Rejects mock data entirely — if SmartAPI returns mock candles, the script aborts
with an error so you never see simulated prices.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# ── Load .env BEFORE any module reads os.getenv() ──────────────────────────
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager
from backend.services.data_aggregator import aggregate_data
from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics


def _check_credentials():
    """Verify SmartAPI credentials are loaded from .env before connecting."""
    api_key = os.getenv("SMARTAPI_API_KEY")
    client_code = os.getenv("SMARTAPI_CLIENT_CODE")
    password = os.getenv("SMARTAPI_PASSWORD")
    if not api_key or api_key.startswith("YOUR_"):
        print("ERROR: SMARTAPI_API_KEY not set in .env (or still a placeholder).")
        print("       Please fill in your real credentials in .env and retry.")
        return False
    if not client_code or client_code.startswith("YOUR_"):
        print("ERROR: SMARTAPI_CLIENT_CODE not set in .env (or still a placeholder).")
        print("       Please fill in your real credentials in .env and retry.")
        return False
    if not password or password.startswith("YOUR_"):
        print("ERROR: SMARTAPI_PASSWORD not set in .env (or still a placeholder).")
        print("       Please fill in your real credentials in .env and retry.")
        return False
    return True


def main():
    # ── 0. Check credentials are present ──────────────────────────
    if not _check_credentials():
        sys.exit(1)

    # ── 1. Prompt for TOTP ─────────────────────────────────────────
    totp = input("Enter SmartAPI TOTP code: ").strip()
    if not totp:
        print("ERROR: TOTP is required. Exiting.")
        sys.exit(1)

    # ── 2. Authenticate SmartAPI ─────────────────────────────────
    # Use SmartAPIManager.create_fresh_client() which reads env vars
    client = SmartAPIManager.create_fresh_client()
    connected = client.connect(totp=totp)
    if not connected:
        print(f"ERROR: SmartAPI login failed: {client.last_error}")
        sys.exit(1)
    print("✅ SmartAPI authenticated.")

    # ── 3. Fetch NIFTY 50 spot 3-minute candles ──────────────────
    symbol = "NSE:NIFTY 50"
    interval = "THREE_MINUTE"
    start_date = "2026-01-01"
    end_date = "2026-06-15"

    print(f"\n📥 Downloading {symbol} {interval} candles from {start_date} to {end_date}...")
    df, status = aggregate_data(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        client=client,
        max_retries=3,
    )

    if status == "mock":
        print("ERROR: Mock data was returned. The user explicitly rejects simulated data.")
        print("       Please ensure SmartAPI credentials are valid and market data is available.")
        sys.exit(1)

    if df is None or df.empty:
        print(f"ERROR: No data returned (status={status}). Cannot proceed.")
        sys.exit(1)

    if status == "partial":
        print("WARN: Some gaps were filled during download. Review the gap log above.")

    print(f"✅ Downloaded {len(df)} candles. Status: {status}")
    print(f"   Date range: {df['time'].min()} -> {df['time'].max()}")

    # Ensure required columns exist
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            print(f"ERROR: Missing column '{col}' in downloaded data.")
            sys.exit(1)

    # ── 4. Load strategy code ────────────────────────────────────
    strategy_path = os.path.join("strategies", "golden_crossover_nifty_selling.py")
    if not os.path.exists(strategy_path):
        print(f"ERROR: Strategy file not found at {strategy_path}")
        sys.exit(1)

    with open(strategy_path, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    # Strategy parameters (injected into sandbox)
    parameters = {
        "name": "GOLDEN CROSSOVER NIFTY SELLING",
        "symbol": symbol,
        "interval": interval,
        "capital": 200000,
        "lot_size": 65,
        "max_trade_cycles_per_day": 6,
        "square_off_time": "15:15",
        "ema_fast": 10,
        "ema_slow": 30,
        "strike_offset_points": 200,
        "sl_points": 20,
        "expiry_type": "WEEKLY",
        "runtime": "legacy_on_bar",
    }

    # ── 5. Run backtest ──────────────────────────────────────────
    print("\n🚀 Running backtest...")
    df_dict = {symbol: df}
    engine = BacktestEngine(
        df_dict=df_dict,
        strategy_code=strategy_code,
        initial_capital=200000.0,
        slippage_pct=0.0005,
        default_trade_type="OPTIONS",
        log_dir="./logs",
        parameters=parameters,
        runtime_type="legacy_on_bar",
        spread_pct=0.01,
        options_slippage_pct=0.01,
    )

    result = engine.run()

    # ── Diagnostic: strategy state ─────────────────────────────────
    if hasattr(engine, 'runtime') and hasattr(engine.runtime, '_strategy_instance'):
        inst = engine.runtime._strategy_instance
        print(f"\n🔍 DIAGNOSTIC:")
        print(f"   Total engine ticks: {len(engine.all_timestamps)}")
        print(f"   Strategy bar_count: {inst.bar_count}")
        print(f"   Strategy symbol: {inst.symbol}")
        print(f"   Strategy ema_fast: {inst.ema_fast}, ema_slow: {inst.ema_slow}")
        print(f"   Strategy current_day: {inst.current_day}")
        print(f"   Strategy trade_cycles: {inst.trade_cycles_today}")
        print(f"   Strategy active_positions: {len(inst.active_positions)}")
    else:
        print(f"\n🔍 DIAGNOSTIC: No strategy instance found")
        print(f"   Total engine ticks: {len(engine.all_timestamps)}")

    # Read first few log entries for errors
    log_path = result.get("log_file_path", "")
    if log_path and os.path.exists(log_path):
        print(f"\n📋 First 20 log events with messages:")
        with open(log_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                try:
                    event = json.loads(line.strip())
                    msgs = event.get("log_messages", [])
                    if msgs:
                        print(f"   [{event.get('timestamp','?')}] {msgs[:3]}")
                except Exception:
                    pass

    # ── 6. Print results ─────────────────────────────────────────
    trades = result.get("trades", [])
    equity_curve = result.get("equity_curve", [])
    final_portfolio = result.get("final_portfolio", {})
    pricing_mode = result.get("pricing_mode", "UNKNOWN")
    run_id = result.get("run_id", "N/A")

    print(f"\n{'='*60}")
    print(f"📊 BACKTEST RESULTS  |  Run ID: {run_id}")
    print(f"{'='*60}")
    print(f"Pricing Mode:        {pricing_mode}")
    print(f"Total Trades:        {len(trades)}")
    print(f"Initial Capital:     ₹200,000")
    print(f"Final Equity:        ₹{final_portfolio.get('equity', 0):,.2f}")
    print(f"Total P&L:           ₹{final_portfolio.get('total_pnl', 0):,.2f}")
    print(f"Total Fees:          ₹{final_portfolio.get('total_fees', 0):,.2f}")
    print(f"Open Positions:      {final_portfolio.get('positions', 0)}")

    if equity_curve:
        equity_values = [e["equity"] for e in equity_curve]
        max_dd = 0.0
        peak = equity_values[0]
        for val in equity_values:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        print(f"Max Drawdown:        ₹{max_dd:,.2f}")

    # Option-specific trade breakdown
    option_trades = [t for t in trades if t.get("instrument_type") == "OPTION"]
    option_entries = [t for t in option_trades if t.get("direction") == "SELL"]
    option_exits = [t for t in option_trades if t.get("direction") == "BUY"]
    print(f"\nOption Trades:       {len(option_trades)}")
    print(f"  Entries (SELL):    {len(option_entries)}")
    print(f"  Exits  (BUY):      {len(option_exits)}")

    # Show first 5 and last 5 trades
    if trades:
        print(f"\nSample trades:")
        for t in trades[:5]:
            print(f"  {t['timestamp']} | {t['direction']} {t.get('option_type','')} {t.get('strike','')} @ ₹{t['price']:.2f} (charges: ₹{t['total_charges']:.2f})")
        if len(trades) > 10:
            print(f"  ... ({len(trades)-10} trades omitted) ...")
        for t in trades[-5:]:
            print(f"  {t['timestamp']} | {t['direction']} {t.get('option_type','')} {t.get('strike','')} @ ₹{t['price']:.2f} (charges: ₹{t['total_charges']:.2f})")

    print(f"\n{'='*60}")
    print(f"✅ Test complete. Log file: {result.get('log_file_path', 'N/A')}")

    # Target comparison (Algorooms reference)
    print(f"\n📌 Algorooms Reference (6 months):")
    print(f"   ~117 trading days | ~550 total trades | Net P&L ~₹37,725 | Max DD ~₹54,506")
    print(f"   (Exact match only possible with real options pricing data)")


if __name__ == "__main__":
    main()
