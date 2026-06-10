"""Insights node — generates narrative bullets AND suggested follow-up questions.

Uses: fast tier LLM, tracer. Returns both insights and suggested_questions in one call.
"""
from __future__ import annotations
import json
import logging
import time

import pandas as pd

from graph.state import AgentState
from utils.llm_factory import get_llm
from utils.tracer import tracer
from utils.compressor import select_relevant_columns
from utils.prompts import INSIGHTS_PROMPT, get_persona_context

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


def _parse_insights_response(text: str) -> tuple[str, list]:
    """Parse LLM response to extract insights string and suggested questions list.

    Tries JSON parse first, falls back to plain text with default questions.
    """
    text = text.strip()

    # Try JSON parse
    try:
        data = json.loads(text)
        insights_list = data.get("insights", [])
        questions = data.get("suggested_questions", [])
        insights_str = "\n".join(insights_list) if isinstance(insights_list, list) else str(insights_list)
        if isinstance(questions, list):
            questions = [q for q in questions if isinstance(q, str) and q.strip()][:3]
        else:
            questions = []
        return insights_str, questions
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from mixed response
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        try:
            data = json.loads(text[start_idx : end_idx + 1])
            insights_list = data.get("insights", [])
            questions = data.get("suggested_questions", [])
            insights_str = "\n".join(insights_list) if isinstance(insights_list, list) else str(insights_list)
            if isinstance(questions, list):
                questions = [q for q in questions if isinstance(q, str) and q.strip()][:3]
            else:
                questions = []
            return insights_str, questions
        except json.JSONDecodeError:
            pass

    # Fallback: treat entire response as plain insights, no questions
    return text, []


def insights_node(state: AgentState) -> dict:
    """LangGraph node: generate 3-5 data-driven insights + 3 follow-up questions."""
    question = state["question"]
    df_path = state["df_path"]
    analysis_result = state.get("analysis_result")
    chat_history = state.get("chat_history", [])
    trace_id = state.get("trace_id", "")
    persona = state.get("persona", "general")

    # Load df for metadata
    try:
        df = pd.read_parquet(df_path)
        rows, cols = len(df), len(df.columns)
        relevant = select_relevant_columns(df, question, max_cols=15)
        col_list = ", ".join(relevant)
    except Exception:
        rows, cols = 0, 0
        col_list = ""

    result_str = str(analysis_result)[:600] if analysis_result else "No result"
    history_block = _format_history_block(chat_history)
    persona_context = get_persona_context(persona)

    llm = get_llm("fast")
    if llm is None:
        tracer.add_event(trace_id, "insights", "warning", {
            "message": "No LLM available for insights generation",
        })
        return {
            "insights": "LLM unavailable — cannot generate insights.",
            "suggested_questions": [],
        }

    model_name = getattr(llm, "model_name", getattr(llm, "model", "unknown"))

    try:
        prompt = INSIGHTS_PROMPT.format(
            question=question,
            analysis_result=result_str,
            history_block=history_block,
            rows=rows,
            cols=cols,
            col_list=col_list,
            persona_context=persona_context,
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

        insights_str, suggested_questions = _parse_insights_response(response.content)

        tracer.add_event(trace_id, "insights", "parsed", {
            "insights_chars": len(insights_str),
            "suggested_questions_count": len(suggested_questions),
        })

        logger.info("Insights node generated %d insights, %d suggested questions.",
                     insights_str.count("✦"), len(suggested_questions))
        return {
            "insights": insights_str,
            "suggested_questions": suggested_questions,
        }

    except Exception as exc:
        logger.warning("Insights generation failed: %s", exc)
        tracer.add_event(trace_id, "insights", "error", {
            "message": f"Insights generation failed: {exc}",
        })
        return {
            "insights": f"Could not generate insights: {exc}",
            "suggested_questions": [],
        }
