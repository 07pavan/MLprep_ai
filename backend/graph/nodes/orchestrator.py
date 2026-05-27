"""Orchestrator node — classifies user intent via LLM with keyword fallback.

Uses: fast tier LLM, tracer, schema compressor.
"""
from __future__ import annotations
import json
import time
import logging

import pandas as pd

from graph.state import AgentState
from utils.llm_factory import get_llm
from utils.tracer import tracer
from utils.compressor import select_relevant_columns
from utils.prompts import ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)


def _keyword_classify(question: str) -> str:
    """Fallback keyword-based intent classification."""
    q = question.lower()
    if any(w in q for w in ["chart", "plot", "graph", "visualize", "trend", "show me", "draw"]):
        return "analysis_and_visualization"
    if any(w in q for w in ["insight", "pattern", "discover", "anomaly", "unusual", "why"]):
        return "insights"
    if any(w in q for w in ["clean", "missing", "quality", "duplicate", "preprocess"]):
        return "cleaning_report"
    return "analysis_only"


def orchestrator_node(state: AgentState) -> dict:
    """LangGraph node: classify user intent."""
    question = state["question"]
    df_path = state["df_path"]
    trace_id = state.get("trace_id", "")

    # Load schema info for prompt
    try:
        df = pd.read_parquet(df_path)
        rows, cols = len(df), len(df.columns)
        relevant = select_relevant_columns(df, question, max_cols=15)
        col_list = ", ".join(relevant)
        dtype_info = ", ".join(f"{c}: {df[c].dtype}" for c in relevant)

        tracer.add_event(trace_id, "orchestrator", "schema_compressed", {
            "total_cols": len(df.columns),
            "selected_cols": len(relevant),
            "selected": relevant,
        })
    except Exception:
        rows, cols, col_list, dtype_info = 0, 0, "", ""

    intent = _keyword_classify(question)  # default fallback

    llm = get_llm("fast")
    if llm is not None:
        try:
            prompt = ORCHESTRATOR_PROMPT.format(
                rows=rows, cols=cols,
                col_list=col_list, dtype_info=dtype_info,
                question=question,
            )

            tracer.add_event(trace_id, "orchestrator", "llm_call", {
                "model": getattr(llm, "model_name", getattr(llm, "model", "unknown")),
                "tier": "fast",
                "prompt_chars": len(prompt),
                "prompt_preview": prompt[:200],
            })

            start = time.perf_counter()
            response = llm.invoke(prompt)
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            tracer.add_event(trace_id, "orchestrator", "llm_response", {
                "response_chars": len(response.content),
                "latency_ms": elapsed_ms,
            })

            text = response.content.strip()

            # Parse JSON response
            parsed = None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                start_idx = text.find("{")
                end_idx = text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    try:
                        parsed = json.loads(text[start_idx : end_idx + 1])
                    except json.JSONDecodeError:
                        pass

            if parsed and "intent" in parsed:
                valid_intents = {
                    "analysis_only",
                    "analysis_and_visualization",
                    "insights",
                    "cleaning_report",
                }
                llm_intent = parsed["intent"]
                if llm_intent in valid_intents:
                    intent = llm_intent

            tracer.add_event(trace_id, "orchestrator", "intent", {
                "intent": intent,
                "source": "llm" if parsed else "keyword",
                "reasoning": parsed.get("reasoning", "") if parsed else "",
            })

        except Exception as exc:
            logger.warning("Orchestrator LLM failed (%s), using keyword fallback", exc)
            tracer.add_event(trace_id, "orchestrator", "warning", {
                "message": f"LLM failed: {exc}, using keyword fallback",
            })
            tracer.add_event(trace_id, "orchestrator", "intent", {
                "intent": intent, "source": "keyword", "reasoning": "",
            })
    else:
        tracer.add_event(trace_id, "orchestrator", "intent", {
            "intent": intent, "source": "keyword", "reasoning": "No LLM available",
        })

    logger.info("Orchestrator final intent: %s for question: %s", intent, question[:80])
    return {"intent": intent}
