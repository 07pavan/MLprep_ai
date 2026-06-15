from __future__ import annotations
import logging
import pandas as pd

from graph.state import AgentState
from tools.quality_tool import check_quality
from tools.cleaning_planner import generate_cleaning_plan

from utils.tracer import tracer

logger = logging.getLogger(__name__)


def cleaning_planner_node(state: AgentState) -> dict:
    """LangGraph node: generate a deterministic cleaning plan for the dataset."""
    df_path = state["df_path"]
    trace_id = state.get("trace_id", "")
    logger.info("Running cleaning planner node for dataset at %s", df_path)
    try:
        df = pd.read_parquet(df_path)
        
        tracer.add_event(trace_id, "cleaning_planner", "start", {
            "rows": len(df),
            "columns": len(df.columns),
        })

        quality_report = check_quality(df)
        plan = generate_cleaning_plan(df, quality_report)

        tracer.add_event(trace_id, "cleaning_planner", "complete", {
            "steps_count": len(plan.get("steps", [])),
        })

        return {
            "cleaning_plan": plan,
            "error": None,
        }
    except Exception as exc:
        logger.error("Cleaning planner node failed: %s", exc, exc_info=True)
        tracer.add_event(trace_id, "cleaning_planner", "error", {
            "message": f"Cleaning planner node failed: {exc}",
        })
        return {
            "error": f"Cleaning planner failed: {exc}"
        }

