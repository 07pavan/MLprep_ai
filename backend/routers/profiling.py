"""Profiling router — dataset profiling, quality checks, and ML readiness endpoints."""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query, Depends

from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from tools.ml_readiness_tool import score_ml_readiness
from utils.session_manager import session_manager
from utils.auth import verify_firebase_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Profiling"])


def _load_session_df(uid: str, session_id: str):
    """Validate session and load the DataFrame."""
    if not session_manager.session_exists(uid, session_id):
        raise HTTPException(status_code=404, detail="Session not found. Upload a file first.")
    return session_manager.load_dataframe(uid, session_id)


@router.get("/profile")
async def get_profile(
    sessionId: str = Query(..., description="Session ID from upload"),
    user: dict = Depends(verify_firebase_token),
):
    """Return comprehensive dataset profiling information."""
    try:
        df = _load_session_df(user["uid"], sessionId)
        return profile_dataset(df)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Profile endpoint error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Profiling failed: {exc}")


@router.get("/quality-check")
async def get_quality_check(
    sessionId: str = Query(..., description="Session ID from upload"),
    user: dict = Depends(verify_firebase_token),
):
    """Return detected data quality issues."""
    try:
        df = _load_session_df(user["uid"], sessionId)
        return check_quality(df)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Quality check endpoint error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Quality check failed: {exc}")


@router.get("/ml-readiness")
async def get_ml_readiness(
    sessionId: str = Query(..., description="Session ID from upload"),
    user: dict = Depends(verify_firebase_token),
):
    """Return ML readiness score and report."""
    try:
        df = _load_session_df(user["uid"], sessionId)
        return score_ml_readiness(df)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ML readiness endpoint error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ML readiness scoring failed: {exc}")
