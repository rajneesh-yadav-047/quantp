"""
Test symmetric trend v7 on all symbols individually + multi-asset combined
"""

import os
import sys
import json
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.backtester import BacktestEngine
from engine.analytics import calculate_metrics

def run_single(symbol, interval, strategy_path):
    catalog_path = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'catalog.json')
    with open(catalog_path, 'r') as f:
        catalog = json.load(f)
    
    key = f"{symbol}_{interval}"
    meta = catalog.get(key)
    if not meta:
        print(f"ERROR: {key} not found in catalog")
        return None, None
    
    df = pd.read_csv(meta['file_path'])
    with open(strategy_path, 'r') as f:
        strategy_code = f.read()
    
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
    metrics = calculate_metrics(res['equity_curve'], res['trades'], 100000.0)
    return res, metrics

def run_multi(symbols_dict, strategy_path):
    with open(strategy_path, 'r') as f:
        strategy_code = f.read()
    
    engine = BacktestEngine(
        df_dict=symbols_dict,
        strategy_code=strategy_code,
        initial_capital=100000.0,
        slippage_pct=0.0005,
        default_trade_type="INTRADAY",
        max_position_size=100,
        log_dir="./logs",
        runtime_type="legacy_on_bar",
    )
    
    res = engine.run()
    metrics = calculate_metrics(res['equity_curve'], res['trades'], 100000.0)
    return res, metrics


if __name__ == "__main__":
    strategy_path = os.path.join(os.path.dirname(__file__), '..', 'strategies', 'symmetric_trend_v7.py')
    catalog_path = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'catalog.json')
    
    with open(catalog_path, 'r') as f:
        catalog = json.load(f)
    
    # ── Individual runs ──
    symbols = {
        'AFC': ('AFC', 'FIFTEEN_MINUTE'),
        'SBIN': ('SBIN', 'FIVE_MINUTE'),
        'IDE': ('IDE', 'FIFTEEN_MINUTE'),
    }
    
    individual = {}
    for name, (sym, interval) in symbols.items():
        print(f"\n{'='*60}")
        print(f"INDIVIDUAL: {sym} | {interval}")
        print(f"{'='*60}")
        r, m = run_single(sym, interval, strategy_path)
        if r:
            individual[name] = (r, m)
            print(f"  Equity: Rs.{r['final_portfolio']['equity']:,.2f} | Return: {m.get('return_pct',0)*100:.2f}% | Trades: {len(r['trades'])}")
    
    # ── Multi-asset run ──
    print(f"\n{'='*60}")
    print("MULTI-ASSET: AFC + SBIN + IDE")
    print(f"{'='*60}")
    
    multi_dict = {}
    for name, (sym, interval) in symbols.items():
        key = f"{sym}_{interval}"
        meta = catalog.get(key)
        if meta:
            multi_dict[sym] = pd.read_csv(meta['file_path'])
    
    r_multi, m_multi = run_multi(multi_dict, strategy_path)
    
    print(f"\n  Final Equity: Rs.{r_multi['final_portfolio']['equity']:,.2f}")
    print(f"  Total P&L:    Rs.{r_multi['final_portfolio']['total_pnl']:,.2f}")
    print(f"  Total Fees:   Rs.{r_multi['final_portfolio']['total_fees']:,.2f}")
    print(f"  Return:       {m_multi.get('return_pct',0)*100:.2f}%")
    print(f"  Sharpe:       {m_multi.get('sharpe_ratio',0):.4f}")
    print(f"  Max DD:       {m_multi.get('max_drawdown',0):.4f}")
    print(f"  Total Trades: {len(r_multi['trades'])}")
    
    if r_multi['trades']:
        print(f"\n  TRADES:")
        for t in r_multi['trades']:
            print(f"    {t['timestamp']} | {t['symbol']:5s} | {t['direction']:4s} | Rs.{t['price']:7.2f} | Qty={t['qty']:3d}")
    
    # ── Summary ──
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, (r, m) in individual.items():
        print(f"  {name:6s} solo:  Rs.{r['final_portfolio']['equity']:,.2f} | {m.get('return_pct',0)*100:+.2f}% | {len(r['trades'])} trades")
    print(f"  {'MULTI':6s} combined: Rs.{r_multi['final_portfolio']['equity']:,.2f} | {m_multi.get('return_pct',0)*100:+.2f}% | {len(r_multi['trades'])} trades")
