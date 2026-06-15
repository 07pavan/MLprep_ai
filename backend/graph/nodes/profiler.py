"""Profiler node — generates comprehensive dataset profile.

Uses: profiler_tool (pure Pandas/NumPy), tracer. No LLM calls.
"""
from __future__ import annotations
import logging

import pandas as pd

from graph.state import AgentState
from tools.profiler_tool import profile_dataset
from utils.tracer import tracer

logger = logging.getLogger(__name__)


def profiler_node(state: AgentState) -> dict:
    """LangGraph node: profile the uploaded dataset."""
    df_path = state["df_path"]
    trace_id = state.get("trace_id", "")

    try:
        df = pd.read_parquet(df_path)
    except Exception as exc:
        tracer.add_event(trace_id, "profiler", "error", {
            "message": f"Failed to load data: {exc}",
        })
        return {
            "profiling_result": {"error": f"Failed to load data: {exc}"},
        }

    tracer.add_event(trace_id, "profiler", "start", {
        "rows": len(df),
        "columns": len(df.columns),
    })

    result = profile_dataset(df)

    tracer.add_event(trace_id, "profiler", "complete", {
        "rows": result["rows"],
        "columns": result["columns"],
        "numerical_count": result["numerical_count"],
        "categorical_count": result["categorical_count"],
    })

    logger.info("Profiler node completed: %d rows, %d cols", result["rows"], result["columns"])

    return {
        "profiling_result": result,
    }
