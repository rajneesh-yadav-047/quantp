"""
Strategies router: strategy CRUD endpoints.
"""

from typing import Optional
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
    runtime_type: Optional[str] = "legacy_on_bar"
    entrypoint: Optional[str] = None


@router.get("")
def list_strategies(db: Session = Depends(get_db)):
    strategies = db.query(StrategyDB).all()
    return [{
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "runtime_type": getattr(s, 'runtime_type', 'legacy_on_bar'),
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
        "runtime_type": getattr(s, 'runtime_type', 'legacy_on_bar'),
        "entrypoint": getattr(s, 'entrypoint', None),
        "version": s.version,
        "updated_at": s.updated_at,
    }


@router.post("")
def create_strategy(req: StrategyCreateRequest, db: Session = Depends(get_db)):
    s = StrategyDB(
        name=req.name,
        description=req.description,
        code=req.code,
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
