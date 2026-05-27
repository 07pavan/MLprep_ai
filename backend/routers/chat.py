"""Chat router — runs the LangGraph for natural language Q&A"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graph.graph import app_graph
from utils.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    sessionId: str
    question: str
    chatHistory: list[dict] = []


@router.post("/chat")
async def chat(req: ChatRequest):
    """Process a natural language question through the LangGraph pipeline."""

    # Validate session
    if not session_manager.session_exists(req.sessionId):
        raise HTTPException(status_code=404, detail="Session not found. Upload a file first.")

    df_path = session_manager.get_data_path(req.sessionId)

    # Build initial state
    initial_state = {
        "session_id": req.sessionId,
        "question": req.question,
        "chat_history": req.chatHistory,
        "df_path": df_path,
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

    # Run the compiled graph
    try:
        config = {"configurable": {"thread_id": req.sessionId}}
        final_state = app_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Graph execution error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {exc}")

    # Build response
    analysis_success = final_state.get("analysis_result") is not None
    viz_success = final_state.get("vega_spec") is not None

    return {
        "success": analysis_success,
        "intent": final_state.get("intent", ""),
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
