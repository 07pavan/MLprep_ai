"""Chat router — runs the LangGraph for natural language Q&A"""
from __future__ import annotations
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graph.graph import app_graph
from utils.session_manager import session_manager
from utils.validators import scan_guardrails
from utils.tracer import tracer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])

# Valid persona values the client may send
VALID_PERSONAS = {"general", "finance", "marketing", "engineering"}


class ChatRequest(BaseModel):
    sessionId: str
    question: str
    chatHistory: list[dict] = []
    persona: str = "general"          # NEW — persona routing


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
        "suggestedQuestions": [],       # NEW
        "clarificationNeeded": False,   # NEW
        "clarificationQuestion": "",    # NEW
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

    # ── Validate persona (fall back gracefully) ───────────────────
    persona = req.persona if req.persona in VALID_PERSONAS else "general"

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
        "persona": persona,                 # NEW — passed to all nodes
        "intent": "",
        "pandas_code": "",
        "analysis_result": None,
        "analysis_error": None,
        "analyst_attempts": 0,
        "vega_spec": None,
        "viz_source": "",
        "viz_attempts": 0,
        "insights": "",
        "suggested_questions": [],          # NEW
        "clarification_needed": False,      # NEW
        "clarification_question": "",       # NEW
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
    clarification_needed = final_state.get("clarification_needed", False)
    # A clarification response is still a "success" — the graph ran correctly
    analysis_success = (
        final_state.get("analysis_result") is not None or clarification_needed
    )
    tracer.end_trace(trace_id, success=analysis_success)

    # ── Build response ────────────────────────────────────────────
    viz_success = final_state.get("vega_spec") is not None

    return {
        "success": analysis_success,
        "intent": final_state.get("intent", ""),
        "traceId": trace_id,
        "persona": persona,
        # ── Analysis ─────────────────────────────────────────────
        "analysis": {
            "success": final_state.get("analysis_result") is not None,
            "resultData": final_state.get("analysis_result"),
            "code": final_state.get("pandas_code", ""),
            "error": final_state.get("analysis_error"),
            "attempts": final_state.get("analyst_attempts", 0),
        },
        # ── Visualization ─────────────────────────────────────────
        "visualization": {
            "success": viz_success,
            "vegaSpec": final_state.get("vega_spec"),
            "source": final_state.get("viz_source", ""),
            "attempts": final_state.get("viz_attempts", 0),
        },
        # ── Insights & follow-ups ─────────────────────────────────
        "insights": final_state.get("insights", ""),
        "suggestedQuestions": final_state.get("suggested_questions", []),   # NEW
        # ── Clarification ─────────────────────────────────────────
        "clarificationNeeded": clarification_needed,                         # NEW
        "clarificationQuestion": final_state.get("clarification_question", ""),  # NEW
        "error": final_state.get("error"),
    }
