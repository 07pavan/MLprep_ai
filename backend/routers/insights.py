"""Insights router — dedicated endpoint that always runs analyst → insights_generator.

Unlike /api/chat (which classifies intent via LLM), this endpoint bypasses the
orchestrator's LLM classification by injecting force_intent="insights" directly
into the graph state. This guarantees that:
  1. The analyst computes data grounded in the actual dataset.
  2. The insights_generator always runs and returns ✦ bullets + suggested questions.
  3. No misclassification can produce an empty insights response.
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graph.graph import app_graph
from utils.session_manager import session_manager
from utils.validators import scan_guardrails
from utils.tracer import tracer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Insights"])

VALID_PERSONAS = {"general", "finance", "marketing", "engineering"}


class InsightsRequest(BaseModel):
    sessionId: str
    question: str
    persona: str = "general"


@router.post("/insights")
async def run_insights(req: InsightsRequest):
    """Run the analyst + insights_generator pipeline for a given question.

    The orchestrator is bypassed (force_intent='insights') so insights are
    ALWAYS generated — no risk of misclassification.
    """
    # ── Guardrails ────────────────────────────────────────────────
    safe, reason = scan_guardrails(req.question)
    if not safe:
        logger.warning("Insights BLOCKED: %s — %s", req.question[:80], reason)
        return {
            "success": False,
            "insights": "",
            "suggestedQuestions": [],
            "analysis": {"success": False, "resultData": None, "code": "", "error": reason},
            "traceId": None,
            "error": reason,
        }

    # ── Validate persona ──────────────────────────────────────────
    persona = req.persona if req.persona in VALID_PERSONAS else "general"

    # ── Validate session ──────────────────────────────────────────
    if not session_manager.session_exists(req.sessionId):
        raise HTTPException(status_code=404, detail="Session not found. Upload a file first.")

    df_path = session_manager.get_data_path(req.sessionId)

    # ── Start trace ───────────────────────────────────────────────
    trace_id = tracer.start_trace(req.sessionId, req.question)

    # ── Build initial state — force insights intent ───────────────
    initial_state = {
        "session_id": req.sessionId,
        "question": req.question,
        "chat_history": [],
        "df_path": df_path,
        "trace_id": trace_id,
        "persona": persona,
        "force_intent": "insights",   # ← key: bypasses orchestrator LLM
        "intent": "",
        "pandas_code": "",
        "analysis_result": None,
        "analysis_error": None,
        "analyst_attempts": 0,
        "vega_spec": None,
        "viz_source": "",
        "viz_attempts": 0,
        "insights": "",
        "suggested_questions": [],
        "clarification_needed": False,
        "clarification_question": "",
        "error": None,
    }

    # ── Run graph ─────────────────────────────────────────────────
    try:
        config = {"configurable": {"thread_id": f"insights_{req.sessionId}"}}
        final_state = app_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Insights graph error: %s", exc, exc_info=True)
        tracer.end_trace(trace_id, success=False)
        raise HTTPException(status_code=500, detail=f"Insights pipeline failed: {exc}")

    # ── Finalize trace ────────────────────────────────────────────
    has_insights = bool(final_state.get("insights", "").strip())
    tracer.end_trace(trace_id, success=has_insights)

    # ── Build response ────────────────────────────────────────────
    return {
        "success": has_insights,
        "traceId": trace_id,
        "insights": final_state.get("insights", ""),
        "suggestedQuestions": final_state.get("suggested_questions", []),
        "analysis": {
            "success": final_state.get("analysis_result") is not None,
            "resultData": final_state.get("analysis_result"),
            "code": final_state.get("pandas_code", ""),
            "error": final_state.get("analysis_error"),
            "attempts": final_state.get("analyst_attempts", 0),
        },
        "error": final_state.get("error"),
    }
