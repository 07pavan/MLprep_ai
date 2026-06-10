"""Firebase Authentication token verification dependency"""
from __future__ import annotations
import logging
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from config.settings import settings

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency to verify Firebase ID tokens.
    
    Returns:
        dict: Decoded token claims containing 'uid', 'email', etc.
    """
    if not settings.ENABLE_AUTH:
        # Development bypass: return dummy user claims
        return {
            "uid": "dev_user_123",
            "email": "dev@example.com",
            "name": "Dev User"
        }

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Bearer token required."
        )

    token = credentials.credentials
    try:
        # Verify the Firebase token
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.warning("Token verification failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired authorization token: {e}"
        )
