"""
GOLDEN CROSSOVER NIFTY SELLING
==============================

Runtime: legacy_on_bar
Type: Option Trading — Indicator Based
Underlying: NIFTY 50, Lot size 65, Exchange NSE
Reference: Spot price

Strategy Logic:
- Every 3-minute candle of NIFTY spot price is evaluated
- EMA(10) crosses above EMA(30) (golden cross) -> SELL PE (ITM put, ATM - 200)
- EMA(10) crosses below EMA(30) (death cross) -> SELL CE (ITM call, ATM + 200)
- Hard stop-loss: 20 points per unit (premium rose 20 pts since entry)
- No take-profit
- Max 6 trade cycles per day
- No new entries after 15:15
- All positions squared off at 15:15
- MIS intraday, Mon-Fri only
- Lot size 65, 1 lot per trade

Parameters (injected via sandbox globals):
  name, symbol, interval, capital, lot_size, max_trade_cycles_per_day,
  square_off_time, ema_fast, ema_slow, strike_offset_points, sl_points,
  expiry_type, runtime
"""

import math
from datetime import datetime, timedelta


class Strategy:
    def __init__(self):
        # Read parameters from sandbox globals (injected by runtime)
        self.name = globals().get("name", "GOLDEN CROSSOVER NIFTY SELLING")
        self.symbol = globals().get("symbol", "NSE:NIFTY 50-EQ")
        self.interval = globals().get("interval", "THREE_MINUTE")
        self.capital = globals().get("capital", 200000)
        self.lot_size = globals().get("lot_size", 65)
        self.max_trade_cycles = globals().get("max_trade_cycles_per_day", 6)
        self.square_off_time = globals().get("square_off_time", "15:15")
        self.ema_fast = globals().get("ema_fast", 10)
        self.ema_slow = globals().get("ema_slow", 30)
        self.strike_offset = globals().get("strike_offset_points", 200)
        self.sl_points = globals().get("sl_points", 20)
        self.expiry_type = globals().get("expiry_type", "WEEKLY")
        self.runtime = globals().get("runtime", "legacy_on_bar")

        # Internal state
        self.ema_fast_val = None
        self.ema_slow_val = None
        self.prev_ema_fast = None
        self.prev_ema_slow = None
        self.bar_count = 0

        # Daily tracking (reset at new day)
        self.current_day = None
        self.trade_cycles_today = 0
        self.day_done = False

        # Active short positions (sold options we need to buy back)
        self.active_positions = []

        # Risk-free rate and IV for BSM fallback inside sandbox
        self.risk_free_rate = 0.065
        self.flat_iv = 0.15

    # ── Main bar handler ─────────────────────────────────────────

    def on_bar(self, state):
        orders = []

        # Parse timestamp
        ts_str = state.current_time
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")

        current_date = ts.date()
        current_time = ts.strftime("%H:%M")

        # Reset daily counters on new day
        if self.current_day != current_date:
            self.current_day = current_date
            self.trade_cycles_today = 0
            self.day_done = False
            self.active_positions = []
            self.ema_fast_val = None
            self.ema_slow_val = None
            self.prev_ema_fast = None
            self.prev_ema_slow = None
            self.bar_count = 0
            print(f"[GCN] New day: {current_date}, symbol={self.symbol}, max_cycles={self.max_trade_cycles}")

        # Skip weekends (safety)
        if ts.weekday() >= 5:
            return []

        # Square off time: 15:15 or later
        sq_hour, sq_min = map(int, self.square_off_time.split(":"))
        if ts.hour > sq_hour or (ts.hour == sq_hour and ts.minute >= sq_min):
            if self.active_positions and not self.day_done:
                for pos in self.active_positions:
                    orders.append(self._close_order(pos))
                self.active_positions = []
                self.day_done = True
                return orders
            self.day_done = True
            return []

        if self.day_done:
            return []

        # Get underlying candle (NIFTY spot)
        candle = state.current_candle.get(self.symbol)
        if candle is None:
            if self.bar_count < 5:
                print(f"[GCN] No candle for symbol={self.symbol} at {ts_str}. Available keys: {list(state.current_candle.keys())}")
            return []

        close_price = float(candle.close)
        self.bar_count += 1

        # Build close history from historical candles + current
        hist = state.historical_candles.get(self.symbol, [])
        closes = [float(c.close) for c in hist] + [close_price]

        min_period = max(self.ema_fast, self.ema_slow)
        if len(closes) < min_period:
            if self.bar_count < 5:
                print(f"[GCN] Not enough history: {len(closes)} < {min_period} at {ts_str}")
            return []

        # Compute EMAs
        self.ema_fast_val = self._ema(closes, self.ema_fast)
        self.ema_slow_val = self._ema(closes, self.ema_slow)

        prev_closes = closes[:-1]
        self.prev_ema_fast = self._ema(prev_closes, self.ema_fast) if len(prev_closes) >= self.ema_fast else self.ema_fast_val
        self.prev_ema_slow = self._ema(prev_closes, self.ema_slow) if len(prev_closes) >= self.ema_slow else self.ema_slow_val

        # Debug print every 1000 bars or on first few
        if self.bar_count <= 3 or self.bar_count % 1000 == 0:
            print(f"[GCN] {ts_str} bar={self.bar_count} close={close_price:.2f} ema10={self.ema_fast_val:.2f} ema30={self.ema_slow_val:.2f} prev10={self.prev_ema_fast:.2f} prev30={self.prev_ema_slow:.2f} cycles={self.trade_cycles_today}")

        # 1. Check stop-loss on existing positions first
        sl_orders = self._check_stop_loss(close_price, ts)
        if sl_orders:
            print(f"[GCN] SL hit at {ts_str}: {len(sl_orders)} orders")
            orders.extend(sl_orders)
            return orders

        # 2. Detect crossover and enter new positions
        golden_cross = (self.prev_ema_fast <= self.prev_ema_slow) and (self.ema_fast_val > self.ema_slow_val)
        death_cross = (self.prev_ema_fast >= self.prev_ema_slow) and (self.ema_fast_val < self.ema_slow_val)

        if golden_cross:
            print(f"[GCN] 🟢 GOLDEN CROSS at {ts_str}! close={close_price:.2f} prev10={self.prev_ema_fast:.2f} prev30={self.prev_ema_slow:.2f} fast10={self.ema_fast_val:.2f} slow30={self.ema_slow_val:.2f}")
            # Long signal -> Sell PE (ITM put, strike = ATM + 200)
            try:
                if self.trade_cycles_today < self.max_trade_cycles:
                    if not any(p["option_type"] == "PE" for p in self.active_positions):
                        spot = close_price
                        strike = self._round_to_nearest_50(spot) + self.strike_offset
                        expiry = self._resolve_weekly_expiry(current_date)
                        entry_premium = self._bsm_price(spot, strike, self._time_to_expiry(ts, expiry), "PE")
                        orders.append(self._entry_order("PE", strike, expiry, entry_premium))
                        self.trade_cycles_today += 1
                        print(f"[GCN] Entry SELL PE strike={strike} expiry={expiry} premium={entry_premium:.2f}")
                    else:
                        print(f"[GCN] Golden cross skipped: already have PE position")
                else:
                    print(f"[GCN] Golden cross skipped: max cycles ({self.max_trade_cycles}) reached")
            except Exception as e:
                print(f"[GCN] ERROR in golden cross entry: {e}")

        elif death_cross:
            print(f"[GCN] 🔴 DEATH CROSS at {ts_str}! close={close_price:.2f} prev10={self.prev_ema_fast:.2f} prev30={self.prev_ema_slow:.2f} fast10={self.ema_fast_val:.2f} slow30={self.ema_slow_val:.2f}")
            # Short signal -> Sell CE (ITM call, strike = ATM - 200)
            try:
                if self.trade_cycles_today < self.max_trade_cycles:
                    if not any(p["option_type"] == "CE" for p in self.active_positions):
                        spot = close_price
                        strike = self._round_to_nearest_50(spot) - self.strike_offset
                        expiry = self._resolve_weekly_expiry(current_date)
                        entry_premium = self._bsm_price(spot, strike, self._time_to_expiry(ts, expiry), "CE")
                        orders.append(self._entry_order("CE", strike, expiry, entry_premium))
                        self.trade_cycles_today += 1
                        print(f"[GCN] Entry SELL CE strike={strike} expiry={expiry} premium={entry_premium:.2f}")
                    else:
                        print(f"[GCN] Death cross skipped: already have CE position")
                else:
                    print(f"[GCN] Death cross skipped: max cycles ({self.max_trade_cycles}) reached")
            except Exception as e:
                print(f"[GCN] ERROR in death cross entry: {e}")

        return orders

    # ── Order builders ───────────────────────────────────────────

    def _entry_order(self, option_type, strike, expiry, entry_premium):
        """Build a SELL order dict for an option leg."""
        # Use the configured underlying symbol (e.g., NSE:NIFTY 50) so the backtester
        # can resolve the underlying spot price for BSM fallback and SL checks.
        symbol = self.symbol
        # Store position tracking for SL and square-off
        self.active_positions.append({
            "symbol": symbol,
            "option_type": option_type,
            "strike": strike,
            "expiry": expiry,
            "entry_price": entry_premium,
            "sl_triggered": False,
        })
        return {
            "symbol": symbol,
            "direction": "SELL",
            "type": "MARKET",
            "price": 0.0,
            "qty": self.lot_size,
            "instrument_type": "OPTION",
            "option_type": option_type,
            "strike": strike,
            "expiry": expiry,
            "action": "SELL",
            "quantity_lots": 1,
            "lot_size": self.lot_size,
            "stop_loss_points": self.sl_points,
        }

    def _close_order(self, pos):
        """Build a BUY order dict to close a short option leg."""
        return {
            "symbol": pos["symbol"],
            "direction": "BUY",
            "type": "MARKET",
            "price": 0.0,
            "qty": self.lot_size,
            "instrument_type": "OPTION",
            "option_type": pos["option_type"],
            "strike": pos["strike"],
            "expiry": pos["expiry"],
            "action": "BUY",
            "quantity_lots": 1,
            "lot_size": self.lot_size,
        }

    # ── Stop-loss check ──────────────────────────────────────────

    def _check_stop_loss(self, spot, ts):
        """Check if any open short position has hit the hard SL (premium + 20 pts)."""
        orders = []
        remaining = []
        for pos in self.active_positions:
            if pos.get("sl_triggered"):
                continue
            T = self._time_to_expiry(ts, pos["expiry"])
            current_premium = self._bsm_price(spot, pos["strike"], T, pos["option_type"])
            entry_premium = pos.get("entry_price")
            if entry_premium is not None and current_premium > entry_premium + self.sl_points:
                # SL hit: buy back the short
                orders.append(self._close_order(pos))
                pos["sl_triggered"] = True
                # Do NOT increment trade_cycles_today here; the cycle was already counted on entry
                continue
            remaining.append(pos)
        self.active_positions = remaining
        return orders

    # ── Black-Scholes (sandbox-safe, uses only math module) ──────

    def _bsm_price(self, S, K, T, option_type):
        """Black-Scholes price using math.erf for standard normal CDF."""
        if T <= 0:
            if option_type == "CE":
                return max(0.0, S - K)
            else:
                return max(0.0, K - S)

        r = self.risk_free_rate
        sigma = self.flat_iv
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        def ndf(x):
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        if option_type == "CE":
            price = S * ndf(d1) - K * math.exp(-r * T) * ndf(d2)
        else:
            price = K * math.exp(-r * T) * ndf(-d2) - S * ndf(-d1)

        return max(0.01, price)

    def _time_to_expiry(self, current_dt, expiry_str):
        """Years to expiry (expiry assumed at 15:30)."""
        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d").replace(hour=15, minute=30, second=0)
        diff = (expiry_dt - current_dt).total_seconds()
        return max(diff / (365.25 * 24 * 3600), 0.0)

    # ── Helpers ──────────────────────────────────────────────────

    def _ema(self, values, period):
        if len(values) < period:
            return values[-1] if values else 0.0
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
        return ema

    def _round_to_nearest_50(self, price):
        return round(price / 50) * 50

    def _resolve_weekly_expiry(self, current_date):
        """Nearest weekly expiry (Thursday)."""
        weekday = current_date.weekday()
        if weekday < 3:          # Mon, Tue, Wed
            days_to_thu = 3 - weekday
        elif weekday == 3:       # Thu
            days_to_thu = 0
        else:                    # Fri, Sat, Sun
            days_to_thu = (3 - weekday) % 7  # 6 for Fri, 5 for Sat, 4 for Sun
        expiry = current_date + timedelta(days=days_to_thu)
        return expiry.strftime("%Y-%m-%d")
