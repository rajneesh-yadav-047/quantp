"""
Strategies router: strategy CRUD endpoints.
"""

import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.database import get_db, StrategyDB

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    code: str
    symbols: Optional[List[str]] = None
    interval: Optional[str] = "FIVE_MINUTE"
    initial_capital: Optional[float] = 100000.0
    max_position_size: Optional[int] = None
    parameters_json: Optional[str] = None
    risk_settings_json: Optional[str] = None
    runtime_type: Optional[str] = "legacy_on_bar"
    entrypoint: Optional[str] = None


@router.get("")
def list_strategies(db: Session = Depends(get_db)):
    strategies = db.query(StrategyDB).all()
    return [{
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "symbols": _canonicalize_symbols(json.loads(s.symbols)) if s.symbols else ["NSE:SBIN-EQ"],
        "interval": s.interval or "FIVE_MINUTE",
        "initial_capital": s.initial_capital or 100000.0,
        "max_position_size": s.max_position_size,
        "parameters_json": s.parameters_json,
        "risk_settings_json": s.risk_settings_json,
        "runtime_type": getattr(s, 'runtime_type', 'legacy_on_bar'),
        "entrypoint": getattr(s, 'entrypoint', None),
        "version": s.version,
        "updated_at": s.updated_at,
    } for s in strategies]


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "code": s.code,
        "symbols": _canonicalize_symbols(json.loads(s.symbols)) if s.symbols else ["NSE:SBIN-EQ"],
        "interval": s.interval or "FIVE_MINUTE",
        "initial_capital": s.initial_capital or 100000.0,
        "max_position_size": s.max_position_size,
        "parameters_json": s.parameters_json,
        "risk_settings_json": s.risk_settings_json,
        "runtime_type": getattr(s, 'runtime_type', 'legacy_on_bar'),
        "entrypoint": getattr(s, 'entrypoint', None),
        "version": s.version,
        "updated_at": s.updated_at,
    }


# --- lightweight canonicalization (no SmartAPI calls) ---

def _canonicalize_sym(s: str) -> str:
    s = s.upper().strip()
    if not s:
        return s
    if ":" in s:
        return s  # already canonical
    # If it already has a suffix like -EQ, -BE, -FUT, prepend NSE: only
    for suffix in ("-EQ", "-BE", "-FUT", "FUT", "-ST", "-SM"):
        if s.endswith(suffix):
            return f"NSE:{s}"
    return f"NSE:{s}-EQ"


def _canonicalize_symbols(symbols: list) -> list:
    return [_canonicalize_sym(s) for s in symbols]


@router.post("")
def create_strategy(req: StrategyCreateRequest, db: Session = Depends(get_db)):
    normalized = _canonicalize_symbols(req.symbols) if req.symbols else None
    s = StrategyDB(
        name=req.name,
        description=req.description,
        code=req.code,
        symbols=json.dumps(normalized) if normalized else '["NSE:SBIN-EQ"]',
        interval=req.interval or "FIVE_MINUTE",
        initial_capital=req.initial_capital or 100000.0,
        max_position_size=req.max_position_size,
        parameters_json=req.parameters_json,
        risk_settings_json=req.risk_settings_json,
        runtime_type=req.runtime_type or "legacy_on_bar",
        entrypoint=req.entrypoint,
        version=1,
    )
    db.add(s)
    db.commit()
    return {"message": "Strategy created successfully", "id": s.id, "runtime_type": s.runtime_type}


@router.put("/{strategy_id}")
def update_strategy(strategy_id: str, req: StrategyCreateRequest, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    s.name = req.name
    s.description = req.description
    s.code = req.code
    if req.symbols is not None:
        s.symbols = json.dumps(_canonicalize_symbols(req.symbols))
    if req.interval is not None:
        s.interval = req.interval
    if req.initial_capital is not None:
        s.initial_capital = req.initial_capital
    if req.max_position_size is not None:
        s.max_position_size = req.max_position_size
    if req.parameters_json is not None:
        s.parameters_json = req.parameters_json
    if req.risk_settings_json is not None:
        s.risk_settings_json = req.risk_settings_json
    s.runtime_type = req.runtime_type or "legacy_on_bar"
    s.entrypoint = req.entrypoint
    s.version = (getattr(s, 'version', 1) or 1) + 1
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Strategy updated successfully", "id": s.id, "version": s.version, "runtime_type": s.runtime_type}


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: str, db: Session = Depends(get_db)):
    s = db.query(StrategyDB).filter(StrategyDB.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    db.delete(s)
    db.commit()
    return {"message": "Strategy deleted successfully"}
