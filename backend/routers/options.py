"""
Options router: option chain, option strategies, and visual strategy builder.
"""

import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db, StrategyDB
from backend.options_models import (
    OptionStrategyDB, OptionLegDB,
    get_option_strategy, get_option_legs,
    resolve_strike_price, generate_strategy_code,
    create_strategy_from_template,
)
from backend.smartapi import SmartAPIClient
from backend.services.smartapi_manager import SmartAPIManager

router = APIRouter(prefix="/api/options", tags=["options"])


# ── Pydantic Models ──

class OptionChainRequest(BaseModel):
    symbol: str = "NSE:NIFTY 50"
    expiry_date: Optional[str] = None


class OptionLegRequest(BaseModel):
    position: str  # BUY or SELL
    option_type: str  # CE or PE
    qty: int
    lot_multiplier: int = 1
    strike_criteria: str = "ATM"
    strike_value: float = 0.0
    strike_type: str = "POINTS"
    sl_enabled: bool = False
    sl_type: str = "PERCENT"
    sl_value: float = 0.0
    sl_on_price: str = "ENTRY"
    tp_enabled: bool = False
    tp_type: str = "PERCENT"
    tp_value: float = 0.0
    tp_on_price: str = "ENTRY"
    trail_sl_enabled: bool = False
    trail_sl_type: str = "PERCENT"
    trail_sl_value: float = 0.0
    trail_sl_step: float = 0.0


class OptionStrategyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    underlying_symbol: str = "NSE:NIFTY 50"
    trade_type: str = "MIS"
    start_time: str = "09:16"
    end_time: str = "15:15"
    expiry_type: str = "WEEKLY"
    strategy_type: str = "indicator"
    initial_capital: float = 1000000.0
    max_position_size: Optional[int] = None
    trade_mon: bool = True
    trade_tue: bool = True
    trade_wed: bool = True
    trade_thu: bool = True
    trade_fri: bool = True
    legs: List[OptionLegRequest]


class TemplateRequest(BaseModel):
    template_name: str  # short_straddle, short_strangle, long_straddle, iron_condor
    underlying_symbol: str = "NSE:NIFTY 50"
    name: Optional[str] = None


# ── Endpoints ──

@router.post("/chain")
def get_option_chain(req: OptionChainRequest):
    """Fetch option chain data for a given underlying symbol.
    
    Note: Angel One SmartAPI does not provide a direct REST option chain endpoint.
    We return mock data that is calibrated to current underlying prices.
    """
    smartapi = SmartAPIManager.get_client()
    if not smartapi or not smartapi.jwt_token:
        # Even if not authenticated, return mock data for testing
        pass
    
    # Try to get live underlying price first
    ltp = None
    if smartapi and smartapi.jwt_token:
        try:
            ltp_data = smartapi.fetch_ltp(req.symbol)
            if ltp_data:
                ltp = ltp_data.get("ltp")
        except Exception:
            pass
    
    # Fall back to mock option chain (always available)
    chain_data = smartapi.fetch_option_chain(req.symbol) if smartapi else None
    if not chain_data:
        # Generate mock data directly
        from backend.smartapi import SmartAPIClient
        mock_client = SmartAPIClient()
        chain_data = mock_client._generate_mock_option_chain(req.symbol)
    
    return {
        "ok": True,
        "data": chain_data,
    }


@router.get("/strategies")
def list_option_strategies(db: Session = Depends(get_db)):
    """List all option strategies."""
    strategies = db.query(OptionStrategyDB).order_by(OptionStrategyDB.created_at.desc()).all()
    return {
        "ok": True,
        "strategies": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "underlying_symbol": s.underlying_symbol,
                "trade_type": s.trade_type,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "expiry_type": s.expiry_type,
                "strategy_type": s.strategy_type,
                "initial_capital": s.initial_capital,
                "max_position_size": s.max_position_size,
                "trade_days": {
                    "mon": s.trade_mon,
                    "tue": s.trade_tue,
                    "wed": s.trade_wed,
                    "thu": s.trade_thu,
                    "fri": s.trade_fri,
                },
                "is_template": s.is_template,
                "template_name": s.template_name,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in strategies
        ]
    }


@router.post("/strategies")
def create_option_strategy(req: OptionStrategyRequest, db: Session = Depends(get_db)):
    """Create a new option strategy with legs."""
    strategy = OptionStrategyDB(
        name=req.name,
        description=req.description,
        underlying_symbol=req.underlying_symbol,
        trade_type=req.trade_type,
        start_time=req.start_time,
        end_time=req.end_time,
        expiry_type=req.expiry_type,
        strategy_type=req.strategy_type,
        initial_capital=req.initial_capital,
        max_position_size=req.max_position_size,
        trade_mon=req.trade_mon,
        trade_tue=req.trade_tue,
        trade_wed=req.trade_wed,
        trade_thu=req.trade_thu,
        trade_fri=req.trade_fri,
    )
    db.add(strategy)
    db.flush()
    
    for i, leg_req in enumerate(req.legs):
        leg = OptionLegDB(
            strategy_id=strategy.id,
            leg_index=i,
            position=leg_req.position,
            option_type=leg_req.option_type,
            qty=leg_req.qty,
            lot_multiplier=leg_req.lot_multiplier,
            strike_criteria=leg_req.strike_criteria,
            strike_value=leg_req.strike_value,
            strike_type=leg_req.strike_type,
            sl_enabled=leg_req.sl_enabled,
            sl_type=leg_req.sl_type,
            sl_value=leg_req.sl_value,
            sl_on_price=leg_req.sl_on_price,
            tp_enabled=leg_req.tp_enabled,
            tp_type=leg_req.tp_type,
            tp_value=leg_req.tp_value,
            tp_on_price=leg_req.tp_on_price,
            trail_sl_enabled=leg_req.trail_sl_enabled,
            trail_sl_type=leg_req.trail_sl_type,
            trail_sl_value=leg_req.trail_sl_value,
            trail_sl_step=leg_req.trail_sl_step,
        )
        db.add(leg)
    
    db.commit()
    db.refresh(strategy)
    
    # Generate code from legs
    legs = get_option_legs(db, strategy.id)
    strategy.code = generate_strategy_code(strategy, legs)
    db.commit()
    
    # Also create a regular StrategyDB entry so it can be backtested
    strategy_db = StrategyDB(
        id=strategy.id,  # Use same ID for easy reference
        name=strategy.name,
        description=strategy.description or f"Option strategy: {strategy.name}",
        code=strategy.code,
        symbols=json.dumps([strategy.underlying_symbol]),
        interval="FIVE_MINUTE",
        initial_capital=strategy.initial_capital,
        max_position_size=strategy.max_position_size,
        runtime_type="legacy_on_bar",
    )
    db.add(strategy_db)
    db.commit()
    
    return {
        "ok": True,
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "code": strategy.code,
        }
    }


@router.post("/strategies/template")
def create_from_template(req: TemplateRequest, db: Session = Depends(get_db)):
    """Create a strategy from a pre-built template."""
    strategy = create_strategy_from_template(
        db=db,
        template_name=req.template_name,
        underlying_symbol=req.underlying_symbol,
        name=req.name,
    )
    
    # Also create a regular StrategyDB entry so it can be backtested
    strategy_db = StrategyDB(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description or f"Option strategy: {strategy.name}",
        code=strategy.code,
        symbols=json.dumps([strategy.underlying_symbol]),
        interval="FIVE_MINUTE",
        initial_capital=strategy.initial_capital,
        max_position_size=strategy.max_position_size,
        runtime_type="legacy_on_bar",
    )
    db.add(strategy_db)
    db.commit()
    
    return {
        "ok": True,
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
        }
    }


@router.get("/strategies/{strategy_id}")
def get_option_strategy_detail(strategy_id: str, db: Session = Depends(get_db)):
    """Get full strategy details including legs."""
    strategy = get_option_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    legs = get_option_legs(db, strategy_id)
    
    return {
        "ok": True,
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "underlying_symbol": strategy.underlying_symbol,
            "trade_type": strategy.trade_type,
            "start_time": strategy.start_time,
            "end_time": strategy.end_time,
            "expiry_type": strategy.expiry_type,
            "strategy_type": strategy.strategy_type,
            "initial_capital": strategy.initial_capital,
            "max_position_size": strategy.max_position_size,
            "code": strategy.code,
            "legs": [
                {
                    "id": l.id,
                    "leg_index": l.leg_index,
                    "position": l.position,
                    "option_type": l.option_type,
                    "qty": l.qty,
                    "lot_multiplier": l.lot_multiplier,
                    "strike_criteria": l.strike_criteria,
                    "strike_value": l.strike_value,
                    "strike_type": l.strike_type,
                    "sl_enabled": l.sl_enabled,
                    "sl_type": l.sl_type,
                    "sl_value": l.sl_value,
                    "sl_on_price": l.sl_on_price,
                    "tp_enabled": l.tp_enabled,
                    "tp_type": l.tp_type,
                    "tp_value": l.tp_value,
                    "tp_on_price": l.tp_on_price,
                    "trail_sl_enabled": l.trail_sl_enabled,
                    "trail_sl_type": l.trail_sl_type,
                    "trail_sl_value": l.trail_sl_value,
                    "trail_sl_step": l.trail_sl_step,
                }
                for l in legs
            ]
        }
    }


@router.delete("/strategies/{strategy_id}")
def delete_option_strategy(strategy_id: str, db: Session = Depends(get_db)):
    """Delete an option strategy and all its legs."""
    strategy = get_option_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Delete legs first
    db.query(OptionLegDB).filter(OptionLegDB.strategy_id == strategy_id).delete()
    db.delete(strategy)
    db.commit()
    
    return {"ok": True, "message": "Strategy deleted"}


@router.get("/templates")
def list_templates():
    """List available pre-built strategy templates."""
    return {
        "ok": True,
        "templates": [
            {
                "id": "short_straddle",
                "name": "Short Straddle",
                "description": "Sell ATM Call and Put at entry time. Square off at exit time.",
                "legs_count": 2,
                "example": "SELL NIFTY 50 ATM CE + SELL NIFTY 50 ATM PE",
            },
            {
                "id": "short_strangle",
                "name": "Short Strangle (1%)",
                "description": "Sell OTM Call and Put at 1% away from ATM. Premium decay strategy.",
                "legs_count": 2,
                "example": "SELL NIFTY 50 OTM+1% CE + SELL NIFTY 50 OTM+1% PE",
            },
            {
                "id": "long_straddle",
                "name": "Long Straddle",
                "description": "Buy ATM Call and Put. Profit from volatility expansion.",
                "legs_count": 2,
                "example": "BUY NIFTY 50 ATM CE + BUY NIFTY 50 ATM PE",
            },
            {
                "id": "iron_condor",
                "name": "Iron Condor",
                "description": "Sell OTM Call/Put, Buy further OTM Call/Put for protection. Limited risk.",
                "legs_count": 4,
                "example": "BUY CE(far) + SELL CE(near) + SELL PE(near) + BUY PE(far)",
            },
        ]
    }
