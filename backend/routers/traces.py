"""Traces router — exposes agent observability data via API"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException

from utils.tracer import tracer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Traces"])


@router.get("/traces")
async def get_traces(limit: int = 50):
    """Return recent trace summaries, newest first."""
    traces = tracer.get_traces(limit=min(limit, 200))
    return {"traces": traces, "count": len(traces)}


@router.get("/traces/{trace_id}")
async def get_trace_detail(trace_id: str):
    """Return full trace with all events."""
    detail = tracer.get_trace_detail(trace_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return detail


@router.delete("/traces")
async def clear_traces():
    """Clear all stored traces."""
    count = tracer.clear()
    logger.info("Cleared %d traces", count)
    return {"cleared": count}
