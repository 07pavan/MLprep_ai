"""Quality node — detects data quality issues.

Uses: quality_tool (pure Pandas/NumPy), tracer. No LLM calls.
"""
from __future__ import annotations
import logging

import pandas as pd

from graph.state import AgentState
from tools.quality_tool import check_quality
from utils.tracer import tracer

logger = logging.getLogger(__name__)


def quality_node(state: AgentState) -> dict:
    """LangGraph node: run data quality checks on the uploaded dataset."""
    df_path = state["df_path"]
    trace_id = state.get("trace_id", "")

    try:
        df = pd.read_parquet(df_path)
    except Exception as exc:
        tracer.add_event(trace_id, "quality", "error", {
            "message": f"Failed to load data: {exc}",
        })
        return {
            "quality_result": {"error": f"Failed to load data: {exc}", "total_issues": 0, "issues": []},
        }

    tracer.add_event(trace_id, "quality", "start", {
        "rows": len(df),
        "columns": len(df.columns),
    })

    result = check_quality(df)

    tracer.add_event(trace_id, "quality", "complete", {
        "total_issues": result["total_issues"],
    })

    logger.info("Quality node completed: %d issues found", result["total_issues"])

    return {
        "quality_result": result,
    }
