"""
Deployments router: manage paper and live deployments per strategy.
"""

import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.database import get_db, DeploymentDB, StrategyDB

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


class DeploymentCreateRequest(BaseModel):
    strategy_id: str
    name: str
    symbol: Optional[str] = None
    mode: str = "paper"  # "paper" or "live"
    config_json: Optional[str] = None


class DeploymentUpdateRequest(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    config_json: Optional[str] = None


@router.get("")
def list_deployments(strategy_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DeploymentDB)
    if strategy_id:
        query = query.filter(DeploymentDB.strategy_id == strategy_id)
    deployments = query.order_by(DeploymentDB.created_at.desc()).all()
    return [{
        "id": d.id,
        "strategy_id": d.strategy_id,
        "name": d.name,
        "symbol": d.symbol,
        "mode": d.mode,
        "status": d.status,
        "config_json": d.config_json,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    } for d in deployments]


@router.get("/{deployment_id}")
def get_deployment(deployment_id: str, db: Session = Depends(get_db)):
    d = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return {
        "id": d.id,
        "strategy_id": d.strategy_id,
        "name": d.name,
        "symbol": d.symbol,
        "mode": d.mode,
        "status": d.status,
        "config_json": d.config_json,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


@router.post("")
def create_deployment(req: DeploymentCreateRequest, db: Session = Depends(get_db)):
    # Verify strategy exists
    s = db.query(StrategyDB).filter(StrategyDB.id == req.strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    d = DeploymentDB(
        strategy_id=req.strategy_id,
        name=req.name,
        symbol=req.symbol,
        mode=req.mode,
        config_json=req.config_json,
    )
    db.add(d)
    db.commit()
    return {"message": "Deployment created successfully", "id": d.id}


@router.put("/{deployment_id}")
def update_deployment(deployment_id: str, req: DeploymentUpdateRequest, db: Session = Depends(get_db)):
    d = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if req.name is not None:
        d.name = req.name
    if req.symbol is not None:
        d.symbol = req.symbol
    if req.mode is not None:
        d.mode = req.mode
    if req.status is not None:
        d.status = req.status
    if req.config_json is not None:
        d.config_json = req.config_json

    d.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Deployment updated successfully", "id": d.id}


@router.delete("/{deployment_id}")
def delete_deployment(deployment_id: str, db: Session = Depends(get_db)):
    d = db.query(DeploymentDB).filter(DeploymentDB.id == deployment_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    db.delete(d)
    db.commit()
    return {"message": "Deployment deleted successfully"}
