"""
Auth router: SmartAPI authentication endpoints.
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.smartapi_manager import SmartAPIManager
from backend.smartapi import SmartAPIClient

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SmartAPIConnectRequest(BaseModel):
    totp: str


@router.get("/smartapi/status")
def smartapi_status():
    return SmartAPIManager.get_status()


@router.post("/smartapi/connect")
def smartapi_connect(req: SmartAPIConnectRequest):
    if not SmartAPIManager.is_configured():
        raise HTTPException(status_code=400, detail="SmartAPI credentials missing in .env file.")

    client = SmartAPIManager.create_fresh_client()
    success = client.connect(totp=req.totp)
    if success:
        SmartAPIManager.set_client(client)
        return {"connection_success": True, "message": "Connected successfully"}
    else:
        return {"connection_success": False, "message": client.last_error}
