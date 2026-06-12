"""
Standalone backtest runner for AFC Downtrend v6.0
"""

import os
import sys
import json
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

# ── Load AFC 15-minute data ──
catalog_path = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'catalog.json')
with open(catalog_path, 'r') as f:
    catalog = json.load(f)

afc_meta = catalog.get('AFC_FIFTEEN_MINUTE')
if not afc_meta:
    print("ERROR: AFC_FIFTEEN_MINUTE not found in catalog")
    sys.exit(1)

df = pd.read_csv(afc_meta['file_path'])
print(f"Loaded AFC data: {len(df)} rows from {df['time'].min()} to {df['time'].max()}")

# ── Load v6 strategy ──
strategy_path = os.path.join(os.path.dirname(__file__), '..', 'strategies', 'afc_downtrend_v6.py')
with open(strategy_path, 'r') as f:
    strategy_code = f.read()

# ── Run backtest ──
engine = BacktestEngine(
    df_dict={"AFC": df},
    strategy_code=strategy_code,
    initial_capital=100000.0,
    slippage_pct=0.0005,
    default_trade_type="INTRADAY",
    max_position_size=50,
    log_dir="./logs",
    runtime_type="legacy_on_bar",
)

res = engine.run()

# ── Results ──
print("\n" + "="*60)
print("BACKTEST RESULTS - AFC Downtrend v6.0")
print("="*60)
print(f"Run ID:        {res['run_id']}")
print(f"Total Trades:  {len(res['trades'])}")
print(f"Final Equity:  Rs.{res['final_portfolio']['equity']:,.2f}")
print(f"Cash:          Rs.{res['final_portfolio']['cash']:,.2f}")
print(f"Total P&L:     Rs.{res['final_portfolio']['total_pnl']:,.2f}")
print(f"Total Fees:    Rs.{res['final_portfolio']['total_fees']:,.2f}")
print(f"Positions:     {res['final_portfolio']['positions']}")

# ── Analytics ──
metrics = calculate_metrics(res['equity_curve'], res['trades'], 100000.0)
print("\n" + "-"*60)
print("METRICS")
print("-"*60)
for k, v in metrics.items():
    if k == 'equity_curve':
        continue
    if k == 'cost_breakdown':
        print(f"  {k}:")
        for ck, cv in v.items():
            print(f"    {ck}: {cv}")
    else:
        print(f"  {k}: {v}")

# ── Trade log ──
if res['trades']:
    print("\n" + "-"*60)
    print("TRADE LOG")
    print("-"*60)
    for t in res['trades']:
        print(f"  {t['timestamp']} | {t['direction']:4s} | Rs.{t['price']:7.2f} | Qty={t['qty']:2d} | Charges=Rs.{t['total_charges']:.2f}")

print("\n" + "="*60)
print(f"Log file: {res['log_file_path']}")
print("="*60)
