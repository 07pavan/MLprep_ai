"""Chat router — runs the LangGraph for natural language Q&A"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graph.graph import app_graph
from utils.session_manager import session_manager
from utils.validators import scan_guardrails
from utils.tracer import tracer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    sessionId: str
    question: str
    chatHistory: list[dict] = []


def _blocked_response(reason: str) -> dict:
    """Return a structured error response without raising an HTTP error."""
    return {
        "success": False,
        "intent": "blocked",
        "traceId": None,
        "analysis": {
            "success": False,
            "resultData": None,
            "code": "",
            "error": reason,
            "attempts": 0,
        },
        "visualization": {
            "success": False,
            "vegaSpec": None,
            "source": "",
            "attempts": 0,
        },
        "insights": "",
        "error": reason,
    }


@router.post("/chat")
async def chat(req: ChatRequest):
    """Process a natural language question through the LangGraph pipeline."""

    # ── Guardrails check ──────────────────────────────────────────
    safe, reason = scan_guardrails(req.question)
    if not safe:
        logger.warning("Chat BLOCKED: %s — %s", req.question[:80], reason)
        return _blocked_response(reason)

    # ── Validate session ──────────────────────────────────────────
    if not session_manager.session_exists(req.sessionId):
        raise HTTPException(status_code=404, detail="Session not found. Upload a file first.")

    df_path = session_manager.get_data_path(req.sessionId)

    # ── Start trace ───────────────────────────────────────────────
    trace_id = tracer.start_trace(req.sessionId, req.question)

    # ── Build initial state ───────────────────────────────────────
    initial_state = {
        "session_id": req.sessionId,
        "question": req.question,
        "chat_history": req.chatHistory,
        "df_path": df_path,
        "trace_id": trace_id,
        "intent": "",
        "pandas_code": "",
        "analysis_result": None,
        "analysis_error": None,
        "analyst_attempts": 0,
        "vega_spec": None,
        "viz_source": "",
        "viz_attempts": 0,
        "insights": "",
        "error": None,
    }

    # ── Run the compiled graph ────────────────────────────────────
    try:
        config = {"configurable": {"thread_id": req.sessionId}}
        final_state = app_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Graph execution error: %s", exc, exc_info=True)
        tracer.end_trace(trace_id, success=False)
        raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {exc}")

    # ── Finalize trace ────────────────────────────────────────────
    analysis_success = final_state.get("analysis_result") is not None
    tracer.end_trace(trace_id, success=analysis_success)

    # ── Build response ────────────────────────────────────────────
    viz_success = final_state.get("vega_spec") is not None

    return {
        "success": analysis_success,
        "intent": final_state.get("intent", ""),
        "traceId": trace_id,
        "analysis": {
            "success": analysis_success,
            "resultData": final_state.get("analysis_result"),
            "code": final_state.get("pandas_code", ""),
            "error": final_state.get("analysis_error"),
            "attempts": final_state.get("analyst_attempts", 0),
        },
        "visualization": {
            "success": viz_success,
            "vegaSpec": final_state.get("vega_spec"),
            "source": final_state.get("viz_source", ""),
            "attempts": final_state.get("viz_attempts", 0),
        },
        "insights": final_state.get("insights", ""),
        "error": final_state.get("error"),
    }
