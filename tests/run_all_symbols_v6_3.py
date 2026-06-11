"""
Generic backtest runner for any symbol using v6.3 strategy
"""

import os
import sys
import json
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

def run_symbol(symbol, interval, strategy_path):
    # ── Load catalog ──
    catalog_path = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'catalog.json')
    with open(catalog_path, 'r') as f:
        catalog = json.load(f)
    
    key = f"{symbol}_{interval}"
    meta = catalog.get(key)
    if not meta:
        print(f"ERROR: {key} not found in catalog")
        return None
    
    df = pd.read_parquet(meta['file_path'])
    print(f"\n{'='*60}")
    print(f"SYMBOL: {symbol} | INTERVAL: {interval}")
    print(f"Rows: {len(df)} | From: {df['time'].min()} | To: {df['time'].max()}")
    print(f"Price range: {df['close'].min():.2f} -> {df['close'].max():.2f}")
    print(f"{'='*60}")
    
    # ── Load strategy ──
    with open(strategy_path, 'r') as f:
        strategy_code = f.read()
    
    # ── Run backtest ──
    engine = BacktestEngine(
        df_dict={symbol: df},
        strategy_code=strategy_code,
        initial_capital=100000.0,
        slippage_pct=0.0005,
        default_trade_type="INTRADAY",
        max_position_size=100,
        log_dir="./logs",
        runtime_type="legacy_on_bar",
    )
    
    res = engine.run()
    
    # ── Results ──
    print(f"\n{'-'*60}")
    print("RESULTS")
    print(f"{'-'*60}")
    print(f"Run ID:        {res['run_id']}")
    print(f"Total Trades:  {len(res['trades'])}")
    print(f"Final Equity:  Rs.{res['final_portfolio']['equity']:,.2f}")
    print(f"Total P&L:     Rs.{res['final_portfolio']['total_pnl']:,.2f}")
    print(f"Total Fees:    Rs.{res['final_portfolio']['total_fees']:,.2f}")
    print(f"Positions:     {res['final_portfolio']['positions']}")
    
    # ── Analytics ──
    metrics = calculate_metrics(res['equity_curve'], res['trades'], 100000.0)
    print(f"\n  return_pct:    {metrics.get('return_pct', 0):.4f}")
    print(f"  win_rate:      {metrics.get('win_rate', 0):.2f}")
    print(f"  sharpe_ratio:  {metrics.get('sharpe_ratio', 0):.4f}")
    print(f"  max_drawdown:  {metrics.get('max_drawdown', 0):.4f}")
    print(f"  total_trades:  {metrics.get('trade_metrics', {}).get('total_trades', 0)}")
    print(f"  gross_profit:  Rs.{metrics.get('trade_metrics', {}).get('gross_profit', 0):.2f}")
    print(f"  gross_loss:    Rs.{metrics.get('trade_metrics', {}).get('gross_loss', 0):.2f}")
    
    # ── Trade log ──
    if res['trades']:
        print(f"\n  TRADES:")
        for t in res['trades']:
            print(f"    {t['timestamp']} | {t['direction']:4s} | Rs.{t['price']:7.2f} | Qty={t['qty']:3d} | Charges=Rs.{t['total_charges']:.2f}")
    
    return res, metrics


if __name__ == "__main__":
    strategy_path = os.path.join(os.path.dirname(__file__), '..', 'strategies', 'afc_downtrend_v6_3_final.py')
    
    # Run on all three symbols
    results = {}
    
    # AFC (already known winner)
    r, m = run_symbol("AFC", "FIFTEEN_MINUTE", strategy_path)
    results['AFC'] = (r, m)
    
    # SBIN (5-min data available)
    r, m = run_symbol("SBIN", "FIVE_MINUTE", strategy_path)
    results['SBIN'] = (r, m)
    
    # IDE (15-min data available)
    r, m = run_symbol("IDE", "FIFTEEN_MINUTE", strategy_path)
    results['IDE'] = (r, m)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY ACROSS ALL SYMBOLS")
    print(f"{'='*60}")
    for sym, (r, m) in results.items():
        if r:
            print(f"  {sym:6s}: Equity=Rs.{r['final_portfolio']['equity']:,.2f} | Return={m.get('return_pct',0)*100:.2f}% | Trades={len(r['trades'])} | Fees=Rs.{r['final_portfolio']['total_fees']:.2f}")
