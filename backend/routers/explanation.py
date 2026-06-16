from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException

from schemas.explanation import ExplanationRequest, ExplanationResponse
from services.explanation_service import get_explanation_service
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v3/explanation", tags=["Dataset Explanation"])

@router.post("/explain", response_model=ExplanationResponse)
async def explain_dataset(
    req: ExplanationRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Generate or retrieve dataset explanations for a specified aspect and persona."""
    user_id = user.get("uid")
    session_id = req.sessionId
    aspect = req.aspect
    persona = req.persona

    # Validate session existence
    if not session_manager.session_exists(user_id, session_id):
        logger.warning(
            "Session not found for explanation: user_id=%s, session_id=%s",
            user_id, session_id
        )
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        service = get_explanation_service()
        result = service.get_explanation(
            user_id=user_id,
            session_id=session_id,
            aspect=aspect,
            persona=persona
        )
        return ExplanationResponse(**result)
    except FileNotFoundError as fnf:
        logger.warning("Dataset file not found: %s", fnf)
        raise HTTPException(status_code=404, detail="Session dataset file not found.")
    except Exception as exc:
        logger.error(
            "Failed to generate explanation: user_id=%s, session_id=%s, error=%s",
            user_id, session_id, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error generating explanation.")
