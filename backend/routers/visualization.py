from __future__ import annotations
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from schemas.visualization import VisualizationGenerateRequest, VisualizationGenerateResponse, VisualizationItem
from services.visualization_service import get_visualization_service
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v3/visualizations", tags=["Auto Visualization"])

VALID_VISUALIZATION_TYPES = {"general", "distribution", "categorical", "correlation", "time_series", "quality"}

@router.post("/generate", response_model=VisualizationGenerateResponse)
async def generate_visualizations_endpoint(
    req: VisualizationGenerateRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Generate and filter automatic visualization recommendations for a session."""
    user_id = user.get("uid")
    session_id = req.sessionId
    viz_type = req.visualizationType
    persona = req.persona

    # Validate visualization type
    if viz_type not in VALID_VISUALIZATION_TYPES:
        logger.warning(
            "Invalid visualizationType requested: user_id=%s, session_id=%s, type=%s",
            user_id, session_id, viz_type
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid visualizationType. Must be one of: {', '.join(VALID_VISUALIZATION_TYPES)}"
        )

    # Validate session existence and ownership
    if not session_manager.session_exists(user_id, session_id):
        logger.warning(
            "Session not found for visualization generation: user_id=%s, session_id=%s",
            user_id, session_id
        )
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        service = get_visualization_service()
        result = service.get_recommendations(
            user_id=user_id,
            session_id=session_id,
            persona=persona
        )

        if not result.get("success", False):
            return VisualizationGenerateResponse(
                success=False,
                errors=[result.get("error") or "Unknown error generating recommendations."]
            )

        recommendations = result.get("recommendations", [])

        # Filter by visualizationType
        # Mapping chart_type values:
        # - distribution: histogram, box
        # - categorical: bar, pie
        # - time_series: line
        # - correlation: scatter, heatmap
        # - quality: quality_chart
        filtered_recs = []
        for rec in recommendations:
            chart_type = rec.get("chart_type")
            if viz_type == "general":
                filtered_recs.append(rec)
            elif viz_type == "distribution" and chart_type in ("histogram", "box"):
                filtered_recs.append(rec)
            elif viz_type == "categorical" and chart_type in ("bar", "pie"):
                filtered_recs.append(rec)
            elif viz_type == "correlation" and chart_type in ("scatter", "heatmap"):
                filtered_recs.append(rec)
            elif viz_type == "time_series" and chart_type == "line":
                filtered_recs.append(rec)
            elif viz_type == "quality" and chart_type == "quality_chart":
                filtered_recs.append(rec)

        # Build response dictionaries
        visualizations = []
        confidence_scores = {}
        explanations = {}
        source_metrics_set = set()

        for item in filtered_recs:
            viz_item = VisualizationItem(**item)
            visualizations.append(viz_item)
            confidence_scores[viz_item.visualization_id] = viz_item.confidence_score
            if viz_item.explanation:
                explanations[viz_item.visualization_id] = viz_item.explanation
            for metric in viz_item.source_metrics:
                source_metrics_set.add(metric)

        return VisualizationGenerateResponse(
            success=True,
            visualizations=visualizations,
            confidenceScores=confidence_scores,
            explanations=explanations,
            sourceMetrics=list(source_metrics_set),
            metadata={
                "total_recommendations": len(recommendations),
                "filtered_recommendations": len(filtered_recs)
            },
            errors=[]
        )

    except FileNotFoundError as fnf:
        logger.warning("Dataset file not found: %s", fnf)
        raise HTTPException(status_code=404, detail="Session dataset file not found.")
    except Exception as exc:
        logger.error(
            "Failed to generate visualizations: user_id=%s, session_id=%s, error=%s",
            user_id, session_id, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error generating visualizations.")
