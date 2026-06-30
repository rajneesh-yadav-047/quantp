# backend/options_models.py
"""
Pydantic models for the options strategy builder and code generator.

Code generation emits a Python `on_bar` function that runs inside the
LegacyRuntime sandbox.  It uses `Order` (injected as a global) to emit
orders with `instrument_type='OPTION'` so the backtester routes them
through the options execution pipeline.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, Session
from backend.database import Base
from engine.runtime.datamodels import Order


# ── Option Leg (builder DTO) ──

class OptionLeg(BaseModel):
    """Single leg of an option strategy (builder DTO)."""
    position: str = Field("BUY", description="BUY or SELL")
    option_type: str = Field("CE", description="CE or PE")
    qty: int = Field(1, description="Number of lots")
    lot_multiplier: int = Field(1, description="Multiplier applied to qty")

    strike_criteria: str = Field("ATM", description="ATM, ITM, OTM, or CUSTOM")
    strike_value: float = Field(0, description="Offset for ITM/OTM or value for CUSTOM")
    strike_type: str = Field("POINTS", description="POINTS or PERCENT")

    sl_enabled: bool = Field(False)
    sl_type: str = Field("PERCENT", description="POINTS or PERCENT")
    sl_value: float = Field(0)
    sl_on_price: Optional[str] = Field(None, description="underlying or premium")

    tp_enabled: bool = Field(False)
    tp_type: str = Field("PERCENT", description="POINTS or PERCENT")
    tp_value: float = Field(0)
    tp_on_price: Optional[str] = Field(None, description="underlying or premium")

    trail_sl_enabled: bool = Field(False)
    trail_sl_type: str = Field("PERCENT", description="POINTS or PERCENT")
    trail_sl_value: float = Field(0)
    trail_sl_step: float = Field(0)


# ── Strategy Template (builder DTO) ──

class StrategyTemplate(BaseModel):
    id: str
    name: str
    description: str
    legs: List[OptionLeg]


# ── Saved Strategy (builder DTO) ──

class SavedStrategy(BaseModel):
    id: int
    name: str
    strategy_type: str
    trade_type: str
    start_time: str
    end_time: str
    expiry_type: str
    initial_capital: float
    trade_days: Dict[str, bool]
    legs: List[OptionLeg]
    code: Optional[str] = None


# ── Database Models ──

class OptionLegDB(Base):
    """Single leg persisted in the database."""
    __tablename__ = "option_legs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("option_strategies.id"), nullable=False)
    position = Column(String, nullable=False)
    option_type = Column(String, nullable=False)
    qty = Column(Integer, nullable=False)
    lot_multiplier = Column(Integer, default=1)
    strike_criteria = Column(String, nullable=False)
    strike_value = Column(Float, default=0)
    strike_type = Column(String, default="POINTS")
    sl_enabled = Column(Boolean, default=False)
    sl_type = Column(String, default="PERCENT")
    sl_value = Column(Float, default=0)
    sl_on_price = Column(String, nullable=True)
    tp_enabled = Column(Boolean, default=False)
    tp_type = Column(String, default="PERCENT")
    tp_value = Column(Float, default=0)
    tp_on_price = Column(String, nullable=True)
    trail_sl_enabled = Column(Boolean, default=False)
    trail_sl_type = Column(String, default="PERCENT")
    trail_sl_value = Column(Float, default=0)
    trail_sl_step = Column(Float, default=0)

    strategy = relationship("OptionStrategyDB", back_populates="legs")

    def to_dto(self) -> OptionLeg:
        return OptionLeg(
            position=self.position,
            option_type=self.option_type,
            qty=self.qty,
            lot_multiplier=self.lot_multiplier,
            strike_criteria=self.strike_criteria,
            strike_value=self.strike_value,
            strike_type=self.strike_type,
            sl_enabled=self.sl_enabled,
            sl_type=self.sl_type,
            sl_value=self.sl_value,
            sl_on_price=self.sl_on_price,
            tp_enabled=self.tp_enabled,
            tp_type=self.tp_type,
            tp_value=self.tp_value,
            tp_on_price=self.tp_on_price,
            trail_sl_enabled=self.trail_sl_enabled,
            trail_sl_type=self.trail_sl_type,
            trail_sl_value=self.trail_sl_value,
            trail_sl_step=self.trail_sl_step,
        )


class OptionStrategyDB(Base):
    """A saved option strategy in the database."""
    __tablename__ = "option_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    strategy_type = Column(String, default="indicator")
    trade_type = Column(String, default="MIS")
    start_time = Column(String, default="09:15")
    end_time = Column(String, default="15:15")
    expiry_type = Column(String, default="WEEKLY")
    initial_capital = Column(Float, default=1000000)
    trade_mon = Column(Boolean, default=True)
    trade_tue = Column(Boolean, default=True)
    trade_wed = Column(Boolean, default=True)
    trade_thu = Column(Boolean, default=True)
    trade_fri = Column(Boolean, default=True)
    underlying_symbol = Column(String, default="NSE:NIFTY 50")
    code = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    legs = relationship("OptionLegDB", back_populates="strategy", cascade="all, delete-orphan", lazy="selectin")

    def to_dto(self, db: Session) -> SavedStrategy:
        legs = [leg.to_dto() for leg in self.legs]
        return SavedStrategy(
            id=self.id,
            name=self.name,
            strategy_type=self.strategy_type,
            trade_type=self.trade_type,
            start_time=self.start_time,
            end_time=self.end_time,
            expiry_type=self.expiry_type,
            initial_capital=self.initial_capital,
            trade_days={
                "mon": self.trade_mon,
                "tue": self.trade_tue,
                "wed": self.trade_wed,
                "thu": self.trade_thu,
                "fri": self.trade_fri,
            },
            legs=legs,
            code=self.code,
        )


# ── Helper functions for DB queries ──

def get_option_strategy(db: Session, strategy_id: int) -> Optional[OptionStrategyDB]:
    """Fetch an option strategy by ID."""
    return db.query(OptionStrategyDB).filter(OptionStrategyDB.id == strategy_id).first()


def get_option_legs(db: Session, strategy_id: int) -> List[OptionLegDB]:
    """Fetch all legs for a given option strategy ID."""
    return db.query(OptionLegDB).filter(OptionLegDB.strategy_id == strategy_id).all()


# ── Code Generator ──

def _extract_name(raw: str) -> str:
    """Strip NSE:/NFO: prefix and -EQ/-BE/-FUT suffix to get bare symbol name."""
    s = raw.upper().strip()
    if s.startswith("NSE:") or s.startswith("NFO:"):
        s = s.split(":", 1)[1]
    for suffix in ("-EQ", "-BE", "-FUT"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def generate_strategy_code(strategy: OptionStrategyDB, legs: List[OptionLegDB]) -> str:
    """Generate Python strategy code from option strategy legs for LegacyRuntime.

    Emits orders with instrument_type='OPTION' so the backtester routes them
    through the options execution pipeline (real premiums, lot sizes, charges).
    """

    leg_configs = []
    for leg in (legs or []):
        leg_configs.append(f"""
    {{
        'position': '{leg.position}',
        'option_type': '{leg.option_type}',
        'qty_lots': {leg.qty},
        'lot_multiplier': {leg.lot_multiplier},
        'strike_criteria': '{leg.strike_criteria}',
        'strike_value': {leg.strike_value},
        'strike_type': '{leg.strike_type}',
        'sl_enabled': {str(leg.sl_enabled)},
        'sl_type': '{leg.sl_type}',
        'sl_value': {leg.sl_value},
    }}""")

    legs_str = ",".join(leg_configs)

    name = getattr(strategy, 'name', 'Untitled') if strategy else 'Untitled'
    underlying_symbol = getattr(strategy, 'underlying_symbol', 'NSE:NIFTY 50') if strategy else 'NSE:NIFTY 50'
    start_time = getattr(strategy, 'start_time', '09:15') if strategy else '09:15'
    end_time = getattr(strategy, 'end_time', '15:15') if strategy else '15:15'
    base_name = _extract_name(underlying_symbol)

    return f'''"""
Auto-generated Option Strategy: {name}
Underlying: {underlying_symbol}  →  base_name: {base_name}
Entry: {start_time} | Exit: {end_time}
"""
from typing import List, Dict, Any
import datetime as dt

# ── Strategy configuration ──
ENTRY_TIME = '{start_time}'
EXIT_TIME = '{end_time}'
UNDERLYING = '{underlying_symbol}'
BASE_NAME = '{base_name}'

LEGS = [{legs_str}
]

# ── Module-level position tracking (persists across ticks) ──
_positions: Dict[str, Dict[str, Any]] = {{}}       # key → leg info
_entered_today: bool = False
_last_entry_date: str = ''


def _get_time_str(current_time):
    """Extract HH:MM from timestamp (handles str, pd.Timestamp, datetime)."""
    try:
        if hasattr(current_time, 'strftime'):
            t = current_time
        else:
            s = str(current_time)
            # Strip timezone offset if present (+05:30)
            if '+' in s:
                s = s.split('+')[0].strip()
            t = dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        return t.strftime('%H:%M')
    except Exception:
        return ''


def _get_date_str(current_time):
    """Extract YYYY-MM-DD from timestamp."""
    try:
        if hasattr(current_time, 'strftime'):
            return current_time.strftime('%Y-%m-%d')
        s = str(current_time)
        if '+' in s:
            s = s.split('+')[0].strip()
        t = dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        return t.strftime('%Y-%m-%d')
    except Exception:
        return ''


def _get_day_of_week(current_time):
    """Get day of week abbreviation."""
    try:
        if hasattr(current_time, 'strftime'):
            return current_time.strftime('%a')
        s = str(current_time)
        if '+' in s:
            s = s.split('+')[0].strip()
        t = dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        return t.strftime('%a')
    except Exception:
        return ''


def _get_expiry(current_time):
    """Return the Thursday of the current week (NIFTY/BANKNIFTY weekly expiry)."""
    try:
        if hasattr(current_time, 'strftime'):
            t = current_time
        else:
            s = str(current_time)
            if '+' in s:
                s = s.split('+')[0].strip()
            t = dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''
    days_to_thu = (3 - t.weekday()) % 7
    expiry = t + dt.timedelta(days=days_to_thu)
    return expiry.date().isoformat()


def _has_positions() -> bool:
    """Check if any options positions are currently open."""
    return any(p.get('qty', 0) != 0 for p in _positions.values())


def _close_all_positions() -> List[Dict[str, Any]]:
    """Generate close orders for all open options positions."""
    orders = []
    for key, pos in _positions.items():
        qty = pos.get('qty', 0)
        if qty == 0:
            continue
        # Reverse direction to close
        direction = 'SELL' if qty > 0 else 'BUY'
        orders.append(Order(
            symbol=UNDERLYING,
            direction=direction,
            type='MARKET',
            price=0,
            quantity=0,
            instrument_type='OPTION',
            expiry=pos.get('expiry', ''),
            strike=pos.get('strike', 0),
            option_type=pos.get('option_type', 'CE'),
            action=direction,
            quantity_lots=abs(qty),
        ))
    return orders


def on_bar(state) -> List[Dict[str, Any]]:
    """
    Entry time: {start_time}
    Exit time: {end_time}
    """
    global _positions, _entered_today, _last_entry_date

    current_time = getattr(state, 'current_time', '')
    time_str = _get_time_str(current_time)
    day_str = _get_day_of_week(current_time)
    date_str = _get_date_str(current_time)
    expiry = _get_expiry(current_time)

    if not time_str or not expiry:
        return []

    # Reset daily entry flag on new day
    if date_str != _last_entry_date:
        _entered_today = False
        _last_entry_date = date_str

    # Check if trading day is enabled
    day_map = {{'Mon': True, 'Tue': True, 'Wed': True, 'Thu': True, 'Fri': True}}
    if not day_map.get(day_str, False):
        return []

    # Get current candle for underlying price
    candles = getattr(state, 'current_candle', {{}})
    underlying_candle = candles.get(UNDERLYING)
    if not underlying_candle:
        return []

    ltp = float(underlying_candle.close)

    # Determine strike step based on underlying
    if 'NIFTY' in UNDERLYING and 'BANK' not in UNDERLYING:
        strike_step = 50
    elif 'BANK' in UNDERLYING or 'BNF' in UNDERLYING or 'BANKNIFTY' in UNDERLYING:
        strike_step = 100
    else:
        strike_step = 10

    base_strike = round(ltp / strike_step) * strike_step
    strikes = [base_strike + i * strike_step for i in range(-10, 11)]

    def find_atm_strike(ltp, strikes):
        return min(strikes, key=lambda s: abs(s - ltp))

    def resolve_strike(ltp, leg, strikes):
        criteria = leg['strike_criteria']
        value = leg['strike_value']
        strike_type = leg['strike_type']
        option_type = leg['option_type']

        atm = find_atm_strike(ltp, strikes)

        if criteria == 'ATM':
            return atm

        if criteria in ('ITM', 'OTM'):
            sorted_strikes = sorted(strikes)
            if option_type == 'CE':
                candidates = [s for s in sorted_strikes if s < ltp] if criteria == 'ITM' else [s for s in sorted_strikes if s > ltp]
            else:
                candidates = [s for s in sorted_strikes if s > ltp] if criteria == 'ITM' else [s for s in sorted_strikes if s < ltp]
            if not candidates:
                return atm
            return candidates[0]

        offset = value if strike_type == 'POINTS' else ltp * (value / 100.0)
        target = ltp + offset
        return min(strikes, key=lambda s: abs(s - target))

    # ── Exit logic: at or after exit time, close all positions ──
    if time_str >= EXIT_TIME:
        if _has_positions():
            orders = _close_all_positions()
            # Clear positions after generating close orders
            _positions = {{}}
            _entered_today = False
            return orders
        return []

    # ── Entry logic: at or after entry time, if no positions, place all legs ──
    if time_str >= ENTRY_TIME and not _entered_today:
        if _has_positions():
            return []

        orders = []
        for leg in LEGS:
            strike = resolve_strike(ltp, leg, strikes)
            qty_lots = leg['qty_lots'] * leg['lot_multiplier']
            direction = leg['position']
            # Track position in module-level dict
            pos_key = f"{{BASE_NAME}}|{{expiry}}|{{strike}}|{{leg['option_type']}}"
            _positions[pos_key] = {{
                'qty': qty_lots if direction == 'BUY' else -qty_lots,
                'expiry': expiry,
                'strike': strike,
                'option_type': leg['option_type'],
                'entry_price': ltp,
            }}
            orders.append(Order(
                symbol=UNDERLYING,
                direction=direction,
                type='MARKET',
                price=0,
                quantity=0,
                instrument_type='OPTION',
                expiry=expiry,
                strike=strike,
                option_type=leg['option_type'],
                action=direction,
                quantity_lots=qty_lots,
            ))
        _entered_today = True
        return orders

    # ── SL check for existing positions ──
    orders = []
    for leg in LEGS:
        if not leg.get('sl_enabled', False):
            continue
        strike = resolve_strike(ltp, leg, strikes)
        pos_key = f"{{BASE_NAME}}|{{expiry}}|{{strike}}|{{leg['option_type']}}"
        pos = _positions.get(pos_key)
        if not pos or pos.get('qty', 0) == 0:
            continue

        sl_value = leg.get('sl_value', 0)
        sl_type = leg.get('sl_type', 'PERCENT')
        entry_price = pos.get('entry_price', 0)

        if entry_price <= 0:
            continue

        # Calculate SL threshold
        if sl_type == 'PERCENT':
            sl_threshold = entry_price * (1 + sl_value / 100)
        else:
            sl_threshold = entry_price + sl_value

        # For shorts: trigger if price > threshold
        # For longs: trigger if price < threshold
        # Using underlying as proxy (simplified for backtesting)
        if leg['position'] == 'SELL' and ltp > sl_threshold:
            direction = 'BUY' if pos['qty'] < 0 else 'SELL'
            orders.append(Order(
                symbol=UNDERLYING,
                direction=direction,
                type='MARKET',
                price=0,
                quantity=0,
                instrument_type='OPTION',
                expiry=expiry,
                strike=strike,
                option_type=leg['option_type'],
                action=direction,
                quantity_lots=abs(pos['qty']),
            ))
            # Remove position after SL hit
            _positions[pos_key] = {{'qty': 0}}
        elif leg['position'] == 'BUY' and ltp < sl_threshold:
            direction = 'SELL' if pos['qty'] > 0 else 'BUY'
            orders.append(Order(
                symbol=UNDERLYING,
                direction=direction,
                type='MARKET',
                price=0,
                quantity=0,
                instrument_type='OPTION',
                expiry=expiry,
                strike=strike,
                option_type=leg['option_type'],
                action=direction,
                quantity_lots=abs(pos['qty']),
            ))
            # Remove position after SL hit
            _positions[pos_key] = {{'qty': 0}}

    return orders
'''


def create_strategy_from_template(
    db: Session,
    template_name: str,
    underlying_symbol: str,
    name: str = None
) -> OptionStrategyDB:
    """Create a pre-built strategy from a template."""
    
    templates = {
        "short_straddle": {
            "name": name or "Short Straddle",
            "description": "Sell ATM Call and Put at entry time. Square off at exit time.",
            "strategy_type": "time-based",
            "legs": [
                {
                    "position": "SELL", "option_type": "CE", "qty": 75,
                    "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS",
                    "sl_enabled": True, "sl_type": "PERCENT", "sl_value": 1.0,
                },
                {
                    "position": "SELL", "option_type": "PE", "qty": 75,
                    "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS",
                    "sl_enabled": True, "sl_type": "PERCENT", "sl_value": 1.0,
                }
            ]
        },
        "short_strangle": {
            "name": name or "Short Strangle (1%)",
            "description": "Sell OTM Call and Put at 1% away from ATM. Square off at exit time.",
            "strategy_type": "time-based",
            "legs": [
                {
                    "position": "SELL", "option_type": "CE", "qty": 75,
                    "strike_criteria": "OTM", "strike_value": 1.0, "strike_type": "PERCENT",
                    "sl_enabled": True, "sl_type": "PERCENT", "sl_value": 1.5,
                },
                {
                    "position": "SELL", "option_type": "PE", "qty": 75,
                    "strike_criteria": "OTM", "strike_value": 1.0, "strike_type": "PERCENT",
                    "sl_enabled": True, "sl_type": "PERCENT", "sl_value": 1.5,
                }
            ]
        },
        "iron_condor": {
            "name": name or "Iron Condor (1.5% wings)",
            "description": "Sell ATM straddle + buy OTM wings at 1.5% away.",
            "strategy_type": "time-based",
            "legs": [
                {"position": "SELL", "option_type": "CE", "qty": 75, "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
                {"position": "SELL", "option_type": "PE", "qty": 75, "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
                {"position": "BUY", "option_type": "CE", "qty": 75, "strike_criteria": "OTM", "strike_value": 1.5, "strike_type": "PERCENT", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
                {"position": "BUY", "option_type": "PE", "qty": 75, "strike_criteria": "OTM", "strike_value": 1.5, "strike_type": "PERCENT", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
            ]
        },
        "long_call_butterfly": {
            "name": name or "Long Call Butterfly",
            "description": "Buy 1 ITM CE, Sell 2 ATM CE, Buy 1 OTM CE. Limited risk, limited profit.",
            "strategy_type": "time-based",
            "legs": [
                {"position": "BUY", "option_type": "CE", "qty": 1, "strike_criteria": "ITM", "strike_value": 1, "strike_type": "POINTS", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
                {"position": "SELL", "option_type": "CE", "qty": 2, "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
                {"position": "BUY", "option_type": "CE", "qty": 1, "strike_criteria": "OTM", "strike_value": 1, "strike_type": "POINTS", "sl_enabled": False, "sl_type": "PERCENT", "sl_value": 0},
            ]
        },
    }

    tpl = templates.get(template_name)
    if not tpl:
        raise ValueError(f"Unknown template: {template_name}")

    db_strategy = OptionStrategyDB(
        name=tpl["name"],
        description=tpl.get("description", ""),
        strategy_type=tpl.get("strategy_type", "time-based"),
        trade_type="MIS",
        start_time="09:15",
        end_time="15:15",
        expiry_type="WEEKLY",
        initial_capital=1000000,
        trade_mon=True,
        trade_tue=True,
        trade_wed=True,
        trade_thu=True,
        trade_fri=True,
        underlying_symbol=underlying_symbol,
    )
    db.add(db_strategy)
    db.commit()
    db.refresh(db_strategy)

    for leg_data in tpl["legs"]:
        leg = OptionLegDB(strategy_id=db_strategy.id, **leg_data)
        db.add(leg)
    db.commit()
    db.refresh(db_strategy)

    db_strategy.code = generate_strategy_code(db_strategy, db_strategy.legs)
    db.commit()

    return db_strategy
