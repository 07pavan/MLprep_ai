from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response

from schemas.story import StoryGenerateRequest, StoryGenerateResponse
from services.story_service import get_story_service
from services.report_export import export_report_to_html, export_report_to_json
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v3/story", tags=["Data Storytelling"])

VALID_REPORT_TYPES = {"executive", "technical", "business", "ML readiness"}

@router.post("/generate", response_model=StoryGenerateResponse)
async def generate_story_endpoint(
    req: StoryGenerateRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Generate a structured AI storytelling business report for a dataset session."""
    user_id = user.get("uid")
    session_id = req.sessionId
    report_type = req.reportType
    persona = req.persona

    # Validate report type
    if report_type not in VALID_REPORT_TYPES:
        logger.warning(
            "Invalid reportType requested: user_id=%s, session_id=%s, type=%s",
            user_id, session_id, report_type
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reportType. Must be one of: {', '.join(VALID_REPORT_TYPES)}"
        )

    # Validate session existence and ownership
    if not session_manager.session_exists(user_id, session_id):
        logger.warning(
            "Session not found for report generation: user_id=%s, session_id=%s",
            user_id, session_id
        )
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        service = get_story_service()
        # Partition cache key by both persona and reportType to avoid collisons
        blended_persona = f"{persona}_{report_type.replace(' ', '_')}"
        result = service.generate_story_report(
            user_id=user_id,
            session_id=session_id,
            persona=blended_persona
        )

        if not result.get("success", False):
            return StoryGenerateResponse(
                success=False,
                errors=result.get("errors", ["Failed to generate report."])
            )

        report_data = result.get("report", {})
        return StoryGenerateResponse(
            success=True,
            report=report_data,
            confidenceScore=report_data.get("confidence_score", 0.85),
            sourceMetadata=report_data.get("sources", []),
            generatedTimestamp=report_data.get("generated_timestamp"),
            errors=[]
        )

    except FileNotFoundError as fnf:
        logger.warning("Dataset file not found: %s", fnf)
        raise HTTPException(status_code=404, detail="Session dataset file not found.")
    except Exception as exc:
        logger.error(
            "Failed to generate storytelling report: user_id=%s, session_id=%s, error=%s",
            user_id, session_id, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error generating report.")

@router.get("/export/pdf/{report_id}")
async def export_story_pdf_endpoint(
    report_id: str,
    user: dict = Depends(verify_firebase_token)
):
    """Retrieve and format a cached report as a print-ready HTML page."""
    user_id = user.get("uid")
    service = get_story_service()
    
    found_report = None
    # Verify cache ownership and cross-user isolation
    for cache_key, cached_item in service._cache.items():
        # Read the owner directly from the stored item (avoids splitting on underscores in user_id)
        cache_user_id = cached_item.get("user_id") or cache_key.split("_")[0]
        report = cached_item.get("data", {}).get("report", {})
        if report and report.get("report_id") == report_id:
            if cache_user_id != user_id:
                logger.warning(
                    "Cross-user report access blocked: user_id=%s attempted to access report owned by user_id=%s",
                    user_id, cache_user_id
                )
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this report.")
            found_report = report
            break

    if not found_report:
        raise HTTPException(status_code=404, detail="Report not found or has expired from cache.")

    html_content = export_report_to_html(found_report)
    return Response(content=html_content, media_type="text/html")

@router.get("/export/json/{report_id}")
async def export_story_json_endpoint(
    report_id: str,
    user: dict = Depends(verify_firebase_token)
):
    """Retrieve a cached report in raw JSON format."""
    user_id = user.get("uid")
    service = get_story_service()
    
    found_report = None
    # Verify cache ownership and cross-user isolation
    for cache_key, cached_item in service._cache.items():
        # Read the owner directly from the stored item (avoids splitting on underscores in user_id)
        cache_user_id = cached_item.get("user_id") or cache_key.split("_")[0]
        report = cached_item.get("data", {}).get("report", {})
        if report and report.get("report_id") == report_id:
            if cache_user_id != user_id:
                logger.warning(
                    "Cross-user report access blocked: user_id=%s attempted to access report owned by user_id=%s",
                    user_id, cache_user_id
                )
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this report.")
            found_report = report
            break

    if not found_report:
        raise HTTPException(status_code=404, detail="Report not found or has expired from cache.")

    json_content = export_report_to_json(found_report)
    return Response(content=json_content, media_type="application/json")
