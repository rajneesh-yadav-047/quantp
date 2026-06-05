import numpy as np
import pandas as pd
from typing import List, Dict, Any, Union
from datetime import datetime

def calculate_metrics(
    equity_curve: List[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    initial_capital: float
) -> Dict[str, Any]:
    """
    Computes professional-grade portfolio metrics from the equity curve and trade logs.
    """
    if not equity_curve:
        return {}

    df_eq = pd.DataFrame(equity_curve)
    df_eq['time'] = pd.to_datetime(df_eq['time'])
    df_eq = df_eq.sort_values('time')
    
    # 1. Basic Stats
    final_equity = df_eq.iloc[-1]['equity']
    total_pnl = final_equity - initial_capital
    return_pct = (total_pnl / initial_capital)

    # 2. Drawdown analysis
    df_eq['peak'] = df_eq['equity'].cummax()
    df_eq['drawdown'] = (df_eq['peak'] - df_eq['equity']) / df_eq['peak']
    max_dd = df_eq['drawdown'].max()

    # 3. Time calculation for CAGR
    start_time = df_eq.iloc[0]['time']
    end_time = df_eq.iloc[-1]['time']
    duration_days = (end_time - start_time).total_seconds() / (24 * 3600)
    # Avoid zero division
    duration_days = max(1.0, duration_days)
    years = duration_days / 365.0
    
    # CAGR
    if final_equity > 0:
        cagr = (final_equity / initial_capital) ** (1.0 / years) - 1.0
    else:
        cagr = -1.0

    # 4. Daily Returns and Sharpe/Sortino/Calmar Ratios
    # Resample to daily frequency (taking last value of each day)
    df_daily = df_eq.set_index('time').resample('D').last().ffill()
    df_daily['daily_pct_change'] = df_daily['equity'].pct_change().fillna(0)
    
    daily_returns = df_daily['daily_pct_change'].values
    mean_return = np.mean(daily_returns)
    std_return = np.std(daily_returns)

    # Risk-free rate (assume 6% annually, ~0.00023 daily)
    rf_daily = 0.06 / 252
    
    # Sharpe Ratio
    if std_return > 0:
        sharpe = ((mean_return - rf_daily) / std_return) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Sortino Ratio (Downside deviation only)
    downside_returns = daily_returns[daily_returns < 0]
    downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0
    if downside_std > 0:
        sortino = ((mean_return - rf_daily) / downside_std) * np.sqrt(252)
    else:
        sortino = 0.0

    # Calmar Ratio
    calmar = cagr / max_dd if max_dd > 0 else 0.0

    # 5. Trade Analysis
    total_trades = len(trades)
    win_rate = 0.0
    profit_factor = 0.0
    expectancy = 0.0
    win_trades_count = 0
    loss_trades_count = 0
    gross_profits = 0.0
    gross_losses = 0.0
    avg_win = 0.0
    avg_loss = 0.0

    # Trade charge aggregates
    total_brokerage = 0.0
    total_stt = 0.0
    total_exc = 0.0
    total_gst = 0.0
    total_sebi = 0.0
    total_stamp = 0.0
    total_fees = 0.0

    if total_trades > 0:
        # Group fills by order ID or compute raw trade PnLs
        # Since matches are standard, we can calculate trade PnLs by tracking FIFO/LIFO or just order ID matching.
        # For simplicity, we can calculate individual trade statistics by matching buying/selling.
        # Alternatively, we can aggregate buy/sell transactions and compute metrics on individual fills.
        # Let's compute trade values
        trade_pnls = []
        for t in trades:
            total_brokerage += t.get('brokerage', 0.0)
            total_stt += t.get('stt', 0.0)
            total_exc += t.get('exc_charges', 0.0)
            total_gst += t.get('gst', 0.0)
            total_sebi += t.get('sebi_charges', 0.0)
            total_stamp += t.get('stamp_duty', 0.0)
            total_fees += t.get('total_charges', 0.0)
            
            # Simple trade profit/loss approximation:
            # PnL can be calculated on a trade closure level, but let's approximate on order fill
            # Or if the trade record contains specific direction and value.
            # A more robust trade catalog aggregates trades by symbol.
            # Let's build a basic FIFO trade matcher to find matching buys/sells and calculate real trade PnLs.
            pass

        # Let's implement FIFO matching to get real trade list with exact PnLs
        matched_trades = match_trades_fifo(trades)
        trade_pnls = [mt['pnl'] for mt in matched_trades]
        
        if trade_pnls:
            wins = [p for p in trade_pnls if p > 0]
            losses = [p for p in trade_pnls if p <= 0]
            win_trades_count = len(wins)
            loss_trades_count = len(losses)
            gross_profits = sum(wins)
            gross_losses = abs(sum(losses))
            
            win_rate = win_trades_count / len(trade_pnls)
            
            avg_win = np.mean(wins) if wins else 0.0
            avg_loss = np.mean(losses) if losses else 0.0
            
            if gross_losses > 0:
                profit_factor = gross_profits / gross_losses
            else:
                profit_factor = 99.0 if gross_profits > 0 else 1.0

            # Expectancy = (Win Rate * Avg Win) + (Loss Rate * Avg Loss)
            loss_rate = 1.0 - win_rate
            expectancy = (win_rate * avg_win) + (loss_rate * avg_loss)

    # 6. Exposure (percentage of bars with open positions)
    steps_with_position = sum(1 for eq in equity_curve if eq.get('margin_used', 0.0) > 0.0)
    total_steps = len(equity_curve)
    exposure = steps_with_position / total_steps if total_steps > 0 else 0.0

    # 7. Capital Efficiency (Net PnL / Max Margin Used)
    max_margin_used = max([eq.get('margin_used', 0.0) for eq in equity_curve])
    capital_efficiency = total_pnl / max_margin_used if max_margin_used > 0 else 0.0

    return {
        "cagr": float(cagr),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "calmar_ratio": float(calmar),
        "max_drawdown": float(max_dd),
        "total_pnl": float(total_pnl),
        "return_pct": float(return_pct),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "expectancy": float(expectancy),
        "exposure": float(exposure),
        "capital_efficiency": float(capital_efficiency),
        "max_margin_used": float(max_margin_used),
        "trade_metrics": {
            "total_trades": total_trades,
            "matched_trades_count": len(trade_pnls) if 'trade_pnls' in locals() else 0,
            "win_trades": win_trades_count,
            "loss_trades": loss_trades_count,
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "gross_profit": float(gross_profits),
            "gross_loss": float(gross_losses)
        },
        "cost_breakdown": {
            "brokerage": float(total_brokerage),
            "stt": float(total_stt),
            "exchange_charges": float(total_exc),
            "gst": float(total_gst),
            "sebi_charges": float(total_sebi),
            "stamp_duty": float(total_stamp),
            "total_fees": float(total_fees)
        }
    }

def match_trades_fifo(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Groups buying and selling fills using a FIFO queue to compute matched trades and PnL.
    """
    matched = []
    # Queues: symbol -> list of (timestamp, price, qty)
    buys: Dict[str, List[List[Any]]] = {}
    sells: Dict[str, List[List[Any]]] = {}

    for t in trades:
        symbol = t['symbol']
        direction = t['direction']
        price = t['price']
        qty = t['qty']
        ts = t['timestamp']
        fee = t.get('total_charges', 0.0) / qty  # Allocate fee per unit

        if direction == "BUY":
            # Check if there are matching sells
            if symbol in sells and sells[symbol]:
                needed = qty
                while needed > 0 and sells[symbol]:
                    sell_item = sells[symbol][0]
                    sell_ts, sell_price, sell_qty, sell_fee = sell_item
                    
                    match_qty = min(needed, sell_qty)
                    # For a SELL position, BUY is cover. PnL = (Sell Price - Buy Price)
                    pnl = (sell_price - price) * match_qty
                    matched.append({
                        "symbol": symbol,
                        "buy_time": ts,
                        "sell_time": sell_ts,
                        "buy_price": price,
                        "sell_price": sell_price,
                        "qty": match_qty,
                        "pnl": pnl - (fee + sell_fee) * match_qty
                    })
                    
                    needed -= match_qty
                    sell_item[2] -= match_qty
                    if sell_item[2] == 0:
                        sells[symbol].pop(0)
                
                if needed > 0:
                    if symbol not in buys:
                        buys[symbol] = []
                    buys[symbol].append([ts, price, needed, fee])
            else:
                if symbol not in buys:
                    buys[symbol] = []
                buys[symbol].append([ts, price, qty, fee])
                
        elif direction == "SELL":
            # Check if there are matching buys
            if symbol in buys and buys[symbol]:
                needed = qty
                while needed > 0 and buys[symbol]:
                    buy_item = buys[symbol][0]
                    buy_ts, buy_price, buy_qty, buy_fee = buy_item
                    
                    match_qty = min(needed, buy_qty)
                    # For a BUY position, SELL is exit. PnL = (Sell Price - Buy Price)
                    pnl = (price - buy_price) * match_qty
                    matched.append({
                        "symbol": symbol,
                        "buy_time": buy_ts,
                        "sell_time": ts,
                        "buy_price": buy_price,
                        "sell_price": price,
                        "qty": match_qty,
                        "pnl": pnl - (buy_fee + fee) * match_qty
                    })
                    
                    needed -= match_qty
                    buy_item[2] -= match_qty
                    if buy_item[2] == 0:
                        buys[symbol].pop(0)
                
                if needed > 0:
                    if symbol not in sells:
                        sells[symbol] = []
                    sells[symbol].append([ts, price, needed, fee])
            else:
                if symbol not in sells:
                    sells[symbol] = []
                sells[symbol].append([ts, price, qty, fee])

    return matched
