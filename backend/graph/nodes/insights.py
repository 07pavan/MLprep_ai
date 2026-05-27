"""Insights node — generates narrative bullet points from analysis results.

Uses: fast tier LLM, tracer.
"""
from __future__ import annotations
import logging
import time

import pandas as pd

from graph.state import AgentState
from utils.llm_factory import get_llm
from utils.tracer import tracer
from utils.prompts import INSIGHTS_PROMPT

logger = logging.getLogger(__name__)


def _format_history_block(chat_history: list, n: int = 3) -> str:
    if not chat_history:
        return ""
    recent = chat_history[-n:]
    lines = ["Recent conversation context:"]
    for turn in reversed(recent):
        q = turn.get("question", "")
        a = str(turn.get("answer", "(no result)"))[:200]
        lines.append(f"  Q: {q}")
        lines.append(f"  A: {a}")
    lines.append("")
    return "\n".join(lines)


def insights_node(state: AgentState) -> dict:
    """LangGraph node: generate 3-5 data-driven insights."""
    question = state["question"]
    df_path = state["df_path"]
    analysis_result = state.get("analysis_result")
    chat_history = state.get("chat_history", [])
    trace_id = state.get("trace_id", "")

    # Load df for metadata
    try:
        df = pd.read_parquet(df_path)
        rows, cols = len(df), len(df.columns)
    except Exception:
        rows, cols = 0, 0

    result_str = str(analysis_result)[:600] if analysis_result else "No result"
    history_block = _format_history_block(chat_history)

    llm = get_llm("fast")
    if llm is None:
        tracer.add_event(trace_id, "insights", "warning", {
            "message": "No LLM available for insights generation",
        })
        return {"insights": "LLM unavailable — cannot generate insights."}

    model_name = getattr(llm, "model_name", getattr(llm, "model", "unknown"))

    try:
        prompt = INSIGHTS_PROMPT.format(
            question=question,
            analysis_result=result_str,
            history_block=history_block,
            rows=rows,
            cols=cols,
        )

        tracer.add_event(trace_id, "insights", "llm_call", {
            "model": model_name, "tier": "fast",
            "prompt_chars": len(prompt),
            "prompt_preview": prompt[:200],
        })

        start = time.perf_counter()
        response = llm.invoke(prompt)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        tracer.add_event(trace_id, "insights", "llm_response", {
            "response_chars": len(response.content),
            "latency_ms": elapsed_ms,
        })

        logger.info("Insights node generated successfully.")
        return {"insights": response.content}

    except Exception as exc:
        logger.warning("Insights generation failed: %s", exc)
        tracer.add_event(trace_id, "insights", "error", {
            "message": f"Insights generation failed: {exc}",
        })
        return {"insights": f"Could not generate insights: {exc}"}
