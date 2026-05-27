"""Insights node — generates narrative bullet points from analysis results"""
from __future__ import annotations
import logging

import pandas as pd
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from graph.state import AgentState
from utils.prompts import INSIGHTS_PROMPT

logger = logging.getLogger(__name__)


def _get_llm():
    try:
        return ChatGroq(
            model=settings.PRIMARY_MODEL,
            temperature=settings.TEMPERATURE,
            groq_api_key=settings.GROQ_API_KEY,
        )
    except Exception:
        try:
            return ChatGoogleGenerativeAI(
                model=settings.BACKUP_MODEL,
                temperature=settings.TEMPERATURE,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        except Exception:
            return None


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

    # Load df for metadata
    try:
        df = pd.read_parquet(df_path)
        rows, cols = len(df), len(df.columns)
    except Exception:
        rows, cols = 0, 0

    result_str = str(analysis_result)[:600] if analysis_result else "No result"
    history_block = _format_history_block(chat_history)

    llm = _get_llm()
    if llm is None:
        return {"insights": "LLM unavailable — cannot generate insights."}

    try:
        prompt = INSIGHTS_PROMPT.format(
            question=question,
            analysis_result=result_str,
            history_block=history_block,
            rows=rows,
            cols=cols,
        )
        response = llm.invoke(prompt)
        logger.info("Insights node generated successfully.")
        return {"insights": response.content}
    except Exception as exc:
        logger.warning("Insights generation failed: %s", exc)
        return {"insights": f"Could not generate insights: {exc}"}
