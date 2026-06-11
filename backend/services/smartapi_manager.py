"""
SmartAPI client manager: centralized global client instance.

Provides thread-safe(ish) access to the shared SmartAPI client
and handles connection state across the application.
"""

import os
from typing import Optional
from backend.smartapi import SmartAPIClient


class SmartAPIManager:
    """
    Manages the global SmartAPI client lifecycle.
    
    Uses a singleton pattern to avoid re-authenticating per request.
    """
    
    _instance: Optional[SmartAPIClient] = None
    
    @classmethod
    def get_client(cls, require_connected: bool = False) -> Optional[SmartAPIClient]:
        """
        Get the global SmartAPI client instance.
        
        Args:
            require_connected: if True, returns None if not authenticated
        """
        if require_connected and (not cls._instance or not cls._instance.jwt_token):
            return None
        return cls._instance
    
    @classmethod
    def set_client(cls, client: SmartAPIClient) -> None:
        """Set the global client instance."""
        cls._instance = client
    
    @classmethod
    def create_fresh_client(cls) -> SmartAPIClient:
        """Create a new client from environment credentials."""
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        return SmartAPIClient(
            api_key=api_key or "",
            client_code=client_code or "",
            password=password or "",
        )
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if credentials are present in environment."""
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        return bool(api_key and client_code and password)
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if global client is authenticated."""
        client = cls._instance
        return bool(client and client.jwt_token and client.is_configured())
    
    @classmethod
    def get_status(cls) -> dict:
        """Get full auth status for frontend."""
        configured = cls.is_configured()
        connected = cls.is_connected()
        client_code = os.getenv("SMARTAPI_CLIENT_CODE") if configured else None
        return {
            "configured": configured,
            "connected": connected,
            "client_code": client_code,
        }
