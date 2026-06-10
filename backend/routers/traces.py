"""Traces router — exposes agent observability data via API"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Depends

from utils.tracer import tracer
from utils.auth import verify_firebase_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Traces"])


@router.get("/traces")
async def get_traces(
    limit: int = 50,
    user: dict = Depends(verify_firebase_token)
):
    """Return recent trace summaries, newest first."""
    traces = tracer.get_traces(limit=min(limit, 200), uid=user["uid"])
    return {"traces": traces, "count": len(traces)}


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    user: dict = Depends(verify_firebase_token)
):
    """Return full trace with all events."""
    detail = tracer.get_trace_detail(trace_id, uid=user["uid"])
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return detail


@router.delete("/traces")
async def clear_traces(
    user: dict = Depends(verify_firebase_token)
):
    """Clear all stored traces for the current user."""
    count = tracer.clear(uid=user["uid"])
    logger.info("User %s cleared %d traces", user["uid"], count)
    return {"cleared": count}
