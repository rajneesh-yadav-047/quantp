"""
Options Strategy DB models for multi-leg option strategies.
Stores visual strategy configurations and their legs.
"""

import uuid
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import Session
from backend.database import Base
from datetime import datetime
from typing import List, Dict, Any, Optional
import json


class OptionStrategyDB(Base):
    """Stores a multi-leg option strategy configuration."""
    __tablename__ = "option_strategies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Strategy configuration
    underlying_symbol = Column(String, nullable=False)  # e.g., NSE:NIFTY 50
    trade_type = Column(String, default="MIS", nullable=False)  # MIS, CNC, BTST
    start_time = Column(String, default="09:16")
    end_time = Column(String, default="15:15")
    expiry_type = Column(String, default="WEEKLY")  # WEEKLY, MONTHLY, NEXT_WEEKLY
    strategy_type = Column(String, default="indicator")  # time-based, indicator-based

    # Risk / Capital settings
    initial_capital = Column(Float, default=1000000.0)
    max_position_size = Column(Integer, nullable=True)

    # Days to trade
    trade_mon = Column(Boolean, default=True)
    trade_tue = Column(Boolean, default=True)
    trade_wed = Column(Boolean, default=True)
    trade_thu = Column(Boolean, default=True)
    trade_fri = Column(Boolean, default=True)

    # Code generation (optional: auto-generated from legs)
    code = Column(Text, nullable=True)

    # Is this a template / pre-built strategy?
    is_template = Column(Boolean, default=False)
    template_name = Column(String, nullable=True)

    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OptionLegDB(Base):
    """Stores a single leg of an option strategy."""
    __tablename__ = "option_legs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    strategy_id = Column(String, nullable=False, index=True)
    leg_index = Column(Integer, nullable=False)  # 0, 1, 2, 3...

    # Leg configuration
    position = Column(String, nullable=False)  # BUY or SELL
    option_type = Column(String, nullable=False)  # CE or PE
    qty = Column(Integer, nullable=False)
    lot_multiplier = Column(Integer, default=1)  # multiples of lot size

    # Strike selection
    strike_criteria = Column(String, default="ATM")  # ATM, ITM, OTM, ATM+POINTS, ATM-PERCENT
    strike_value = Column(Float, default=0.0)  # points or percent offset
    strike_type = Column(String, default="POINTS")  # POINTS, PERCENT

    # Stop Loss
    sl_enabled = Column(Boolean, default=False)
    sl_type = Column(String, default="PERCENT")  # PERCENT, POINTS
    sl_value = Column(Float, default=0.0)
    sl_on_price = Column(String, default="ENTRY")  # ENTRY, PREMIUM

    # Take Profit
    tp_enabled = Column(Boolean, default=False)
    tp_type = Column(String, default="PERCENT")  # PERCENT, POINTS
    tp_value = Column(Float, default=0.0)
    tp_on_price = Column(String, default="ENTRY")  # ENTRY, PREMIUM

    # Trail SL (optional)
    trail_sl_enabled = Column(Boolean, default=False)
    trail_sl_type = Column(String, default="PERCENT")  # PERCENT, POINTS
    trail_sl_value = Column(Float, default=0.0)
    trail_sl_step = Column(Float, default=0.0)

    # Entry condition (for indicator-based)
    entry_condition = Column(Text, nullable=True)  # JSON of condition rules

    created_at = Column(DateTime, default=datetime.utcnow)


def get_option_strategy(db: Session, strategy_id: str) -> Optional[OptionStrategyDB]:
    return db.query(OptionStrategyDB).filter(OptionStrategyDB.id == strategy_id).first()


def get_option_legs(db: Session, strategy_id: str) -> List[OptionLegDB]:
    return db.query(OptionLegDB).filter(OptionLegDB.strategy_id == strategy_id).order_by(OptionLegDB.leg_index).all()


def resolve_strike_price(
    underlying_ltp: float,
    strike_criteria: str,
    strike_value: float,
    strike_type: str,
    option_type: str,
    available_strikes: List[float]
) -> float:
    """
    Resolve strike selection (ATM, ITM, OTM, ATM+points, ATM+percent) to actual strike price.
    
    Args:
        underlying_ltp: Current underlying price
        strike_criteria: ATM, ITM, OTM, ATM+POINTS, ATM-PERCENT
        strike_value: offset value
        strike_type: POINTS or PERCENT
        option_type: CE or PE
        available_strikes: list of available strike prices from option chain
    """
    if not available_strikes:
        available_strikes = [underlying_ltp]

    # Find nearest ATM
    atm_strike = min(available_strikes, key=lambda s: abs(s - underlying_ltp))
    
    sorted_strikes = sorted(available_strikes)
    
    if strike_criteria == "ATM":
        return atm_strike
    
    if strike_criteria in ("ITM", "OTM"):
        # For CE: ITM = strike < ltp, OTM = strike > ltp
        # For PE: ITM = strike > ltp, OTM = strike < ltp
        itm_direction = -1 if option_type == "CE" else 1
        otm_direction = 1 if option_type == "CE" else -1
        
        direction = itm_direction if strike_criteria == "ITM" else otm_direction
        
        # Find strikes in the direction
        if direction > 0:  # higher strikes
            candidates = [s for s in sorted_strikes if s > atm_strike]
        else:  # lower strikes
            candidates = [s for s in sorted_strikes if s < atm_strike]
            candidates = sorted(candidates, reverse=True)
        
        if not candidates:
            return atm_strike
        return candidates[0]  # 1st ITM/OTM
    
    # ATM + POINTS / PERCENT
    if strike_type == "PERCENT":
        offset = underlying_ltp * (strike_value / 100.0)
    else:
        offset = strike_value
    
    if strike_criteria.startswith("ATM+") or strike_value > 0:
        target = underlying_ltp + offset
    else:
        target = underlying_ltp - offset
    
    return min(available_strikes, key=lambda s: abs(s - target))


def generate_strategy_code(strategy: OptionStrategyDB, legs: List[OptionLegDB]) -> str:
    """Generate Python strategy code from option strategy legs for LegacyRuntime."""
    
    # Build leg configurations as Python dict literals
    leg_configs = []
    for leg in legs:
        leg_configs.append(f"""
    {{
        'position': '{leg.position}',
        'option_type': '{leg.option_type}',
        'qty': {leg.qty},
        'lot_multiplier': {leg.lot_multiplier},
        'strike_criteria': '{leg.strike_criteria}',
        'strike_value': {leg.strike_value},
        'strike_type': '{leg.strike_type}',
        'sl_enabled': {str(leg.sl_enabled).lower()},
        'sl_type': '{leg.sl_type}',
        'sl_value': {leg.sl_value},
    }},""")
    
    legs_str = ",".join(leg_configs)
    
    return f'''"""
Auto-generated Option Strategy: {strategy.name}
Underlying: {strategy.underlying_symbol}
Entry: {strategy.start_time} | Exit: {strategy.end_time}
"""
from typing import List, Dict, Any
import datetime as dt

# Strategy configuration
ENTRY_TIME = '{strategy.start_time}'
EXIT_TIME = '{strategy.end_time}'
UNDERLYING = '{strategy.underlying_symbol}'

LEGS = [{legs_str}
]


def _get_time_str(current_time):
    """Extract HH:MM from timestamp."""
    try:
        t = dt.datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
        return t.strftime('%H:%M')
    except:
        return ''


def _get_day_of_week(current_time):
    """Get day of week abbreviation."""
    try:
        t = dt.datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
        return t.strftime('%a')
    except:
        return ''


def _has_positions(state):
    """Check if we have any open positions."""
    positions = getattr(state, 'positions', {{}})
    return any(pos.qty != 0 for pos in positions.values())


def _close_all_positions(state):
    """Generate close orders for all open positions."""
    orders = []
    positions = getattr(state, 'positions', {{}})
    for sym, pos in positions.items():
        if pos.qty > 0:
            orders.append({{'symbol': sym, 'direction': 'SELL', 'type': 'MARKET', 'price': 0, 'qty': abs(pos.qty)}})
        elif pos.qty < 0:
            orders.append({{'symbol': sym, 'direction': 'BUY', 'type': 'MARKET', 'price': 0, 'qty': abs(pos.qty)}})
    return orders


def on_bar(state) -> List[Dict[str, Any]]:
    """
    Entry time: {strategy.start_time}
    Exit time: {strategy.end_time}
    """
    current_time = getattr(state, 'current_time', '')
    time_str = _get_time_str(current_time)
    day_str = _get_day_of_week(current_time)
    
    if not time_str:
        return []
    
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
    
    # Exit logic: at end time, close all positions
    if time_str == EXIT_TIME:
        return _close_all_positions(state)
    
    # Entry logic: at start time, if no positions, place all legs
    if time_str == ENTRY_TIME:
        if _has_positions(state):
            return []
        
        orders = []
        for leg in LEGS:
            strike = resolve_strike(ltp, leg, strikes)
            # For backtesting, use a synthetic symbol based on underlying + strike + option type
            symbol = f"{{UNDERLYING}}-{{leg['option_type']}}-{{int(strike)}}"
            qty = leg['qty'] * leg['lot_multiplier']
            direction = leg['position']
            orders.append({{
                'symbol': symbol,
                'direction': direction,
                'type': 'MARKET',
                'price': 0,
                'qty': qty,
            }})
        return orders
    
    # Check SL for existing positions
    positions = getattr(state, 'positions', {{}})
    orders = []
    for leg in LEGS:
        if not leg.get('sl_enabled', False):
            continue
        strike = resolve_strike(ltp, leg, strikes)
        symbol = f"{{UNDERLYING}}-{{leg['option_type']}}-{{int(strike)}}"
        pos = positions.get(symbol)
        if not pos or pos.qty == 0:
            continue
        
        sl_value = leg.get('sl_value', 0)
        sl_type = leg.get('sl_type', 'PERCENT')
        entry_price = pos.avg_price
        
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
            if pos.qty > 0:
                orders.append({{'symbol': symbol, 'direction': 'SELL', 'type': 'MARKET', 'price': 0, 'qty': abs(pos.qty)}})
            elif pos.qty < 0:
                orders.append({{'symbol': symbol, 'direction': 'BUY', 'type': 'MARKET', 'price': 0, 'qty': abs(pos.qty)}})
        elif leg['position'] == 'BUY' and ltp < sl_threshold:
            if pos.qty > 0:
                orders.append({{'symbol': symbol, 'direction': 'SELL', 'type': 'MARKET', 'price': 0, 'qty': abs(pos.qty)}})
            elif pos.qty < 0:
                orders.append({{'symbol': symbol, 'direction': 'BUY', 'type': 'MARKET', 'price': 0, 'qty': abs(pos.qty)}})
    
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
        "long_straddle": {
            "name": name or "Long Straddle",
            "description": "Buy ATM Call and Put. Profit from volatility expansion.",
            "strategy_type": "indicator",
            "legs": [
                {
                    "position": "BUY", "option_type": "CE", "qty": 75,
                    "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS",
                },
                {
                    "position": "BUY", "option_type": "PE", "qty": 75,
                    "strike_criteria": "ATM", "strike_value": 0, "strike_type": "POINTS",
                }
            ]
        },
        "iron_condor": {
            "name": name or "Iron Condor",
            "description": "Sell OTM Call/Put, Buy further OTM Call/Put for protection.",
            "strategy_type": "time-based",
            "legs": [
                {
                    "position": "BUY", "option_type": "CE", "qty": 75,
                    "strike_criteria": "OTM", "strike_value": 2.0, "strike_type": "PERCENT",
                },
                {
                    "position": "SELL", "option_type": "CE", "qty": 75,
                    "strike_criteria": "OTM", "strike_value": 1.0, "strike_type": "PERCENT",
                    "sl_enabled": True, "sl_type": "PERCENT", "sl_value": 2.0,
                },
                {
                    "position": "SELL", "option_type": "PE", "qty": 75,
                    "strike_criteria": "OTM", "strike_value": 1.0, "strike_type": "PERCENT",
                    "sl_enabled": True, "sl_type": "PERCENT", "sl_value": 2.0,
                },
                {
                    "position": "BUY", "option_type": "PE", "qty": 75,
                    "strike_criteria": "OTM", "strike_value": 2.0, "strike_type": "PERCENT",
                }
            ]
        }
    }
    
    template = templates.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")
    
    strategy = OptionStrategyDB(
        name=template["name"],
        description=template["description"],
        underlying_symbol=underlying_symbol,
        strategy_type=template["strategy_type"],
        is_template=True,
        template_name=template_name,
        code=generate_strategy_code(None, None)  # Will be generated after legs are created
    )
    db.add(strategy)
    db.flush()
    
    for i, leg_data in enumerate(template["legs"]):
        leg = OptionLegDB(strategy_id=strategy.id, leg_index=i, **leg_data)
        db.add(leg)
    
    db.commit()
    db.refresh(strategy)
    
    # Generate code
    legs = get_option_legs(db, strategy.id)
    strategy.code = generate_strategy_code(strategy, legs)
    db.commit()
    
    return strategy
