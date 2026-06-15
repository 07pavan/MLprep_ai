"""ML Readiness node — scores the dataset for ML training readiness.

Uses: ml_readiness_tool (deterministic scoring), tracer. No LLM calls.
"""
from __future__ import annotations
import logging

import pandas as pd

from graph.state import AgentState
from tools.ml_readiness_tool import score_ml_readiness
from utils.tracer import tracer

logger = logging.getLogger(__name__)


def ml_readiness_node(state: AgentState) -> dict:
    """LangGraph node: compute ML readiness score for the uploaded dataset."""
    df_path = state["df_path"]
    trace_id = state.get("trace_id", "")

    try:
        df = pd.read_parquet(df_path)
    except Exception as exc:
        tracer.add_event(trace_id, "ml_readiness", "error", {
            "message": f"Failed to load data: {exc}",
        })
        return {
            "ml_readiness_result": {"error": f"Failed to load data: {exc}", "score": 0, "grade": "F"},
        }

    tracer.add_event(trace_id, "ml_readiness", "start", {
        "rows": len(df),
        "columns": len(df.columns),
    })

    result = score_ml_readiness(df)

    tracer.add_event(trace_id, "ml_readiness", "complete", {
        "score": result["score"],
        "grade": result["grade"],
        "problems_count": len(result["problems"]),
    })

    logger.info("ML Readiness node completed: score=%d grade=%s", result["score"], result["grade"])

    return {
        "ml_readiness_result": result,
    }
