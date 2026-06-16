from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException

from schemas.insight import InsightsRequest, InsightsResponse
from services.insight_service import get_insight_service
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v3/insights", tags=["Proactive Insights"])

VALID_INSIGHT_TYPES = {"general", "statistical", "quality", "ml_readiness", "business"}

@router.post("/generate", response_model=InsightsResponse)
async def generate_insights_endpoint(
    req: InsightsRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Generate proactive insights for a session dataset."""
    user_id = user.get("uid")
    session_id = req.sessionId
    insight_type = req.insightType
    persona = req.persona

    # Validate insight type
    if insight_type not in VALID_INSIGHT_TYPES:
        logger.warning(
            "Invalid insightType requested: user_id=%s, session_id=%s, type=%s",
            user_id, session_id, insight_type
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid insightType. Must be one of: {', '.join(VALID_INSIGHT_TYPES)}"
        )

    # Validate session ownership and existence
    if not session_manager.session_exists(user_id, session_id):
        logger.warning(
            "Session not found for insights generation: user_id=%s, session_id=%s",
            user_id, session_id
        )
        raise HTTPException(status_code=404, detail="Session not found.")

    # Map insightType category parameter for the service
    category_map = {
        "general": "all",
        "statistical": "statistical",
        "quality": "quality",
        "ml_readiness": "ml_readiness",
        "business": "business"
    }
    category = category_map.get(insight_type, "all")

    try:
        service = get_insight_service()
        result = service.generate_insights(
            user_id=user_id,
            session_id=session_id,
            category=category,
            min_severity="LOW"
        )
        return InsightsResponse(**result)
    except FileNotFoundError as fnf:
        logger.warning("Dataset file not found: %s", fnf)
        raise HTTPException(status_code=404, detail="Session dataset file not found.")
    except Exception as exc:
        logger.error(
            "Failed to generate proactive insights: user_id=%s, session_id=%s, error=%s",
            user_id, session_id, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error generating insights.")
