"""
Dataset Groups router: CRUD for named symbol baskets.

Endpoints:
  GET    /api/groups              - list all groups
  POST   /api/groups              - create a new group
  PUT    /api/groups/{name}       - update group symbols
  DELETE /api/groups/{name}       - delete a group
  GET    /api/groups/{name}/symbols - list symbols for a group
"""

import os
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/groups", tags=["groups"])

_GROUPS_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "datasets", "groups.yaml"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_groups() -> Dict[str, Any]:
    if not os.path.exists(_GROUPS_CONFIG_PATH):
        return {}
    with open(_GROUPS_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}


def _save_groups(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_GROUPS_CONFIG_PATH), exist_ok=True)
    with open(_GROUPS_CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=True)


def _flat_groups(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Flatten YAML structure (handling optional 'custom_groups' sub-key)."""
    result: Dict[str, List[str]] = {}
    for k, v in data.items():
        if k == "custom_groups" and isinstance(v, dict):
            for ck, cv in (v or {}).items():
                result[ck] = list(cv or [])
        elif isinstance(v, list):
            result[k] = list(v)
    return result


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class GroupCreate(BaseModel):
    name: str
    symbols: List[str]


class GroupUpdate(BaseModel):
    symbols: List[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_groups():
    """Return all dataset groups."""
    raw = _load_groups()
    groups = _flat_groups(raw)
    return [
        {"name": k, "symbols": v, "count": len(v)}
        for k, v in sorted(groups.items())
    ]


@router.post("")
def create_group(body: GroupCreate):
    """Create a new dataset group."""
    raw = _load_groups()
    groups = _flat_groups(raw)
    name = body.name.upper().replace(" ", "_")
    if name in groups:
        raise HTTPException(status_code=409, detail=f"Group '{name}' already exists.")
    groups[name] = [s.upper() for s in body.symbols]
    _save_groups(groups)
    return {"name": name, "symbols": groups[name], "count": len(groups[name])}


@router.put("/{name}")
def update_group(name: str, body: GroupUpdate):
    """Replace symbols in a group."""
    name = name.upper()
    raw = _load_groups()
    groups = _flat_groups(raw)
    if name not in groups:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found.")
    groups[name] = [s.upper() for s in body.symbols]
    _save_groups(groups)
    return {"name": name, "symbols": groups[name], "count": len(groups[name])}


@router.delete("/{name}")
def delete_group(name: str):
    """Delete a dataset group."""
    name = name.upper()
    raw = _load_groups()
    groups = _flat_groups(raw)
    if name not in groups:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found.")
    del groups[name]
    _save_groups(groups)
    return {"deleted": name}


@router.get("/{name}/symbols")
def get_group_symbols(name: str):
    """Return the symbols for a named group."""
    name = name.upper()
    raw = _load_groups()
    groups = _flat_groups(raw)
    if name not in groups:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found.")
    return {"name": name, "symbols": groups[name]}
