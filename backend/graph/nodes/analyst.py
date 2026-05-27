"""Analyst node — generates and self-corrects pandas code"""
from __future__ import annotations
import logging
import re

import pandas as pd
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from graph.state import AgentState
from tools.pandas_tool import PandasTool
from utils.prompts import ANALYST_PROMPT, ANALYST_FIX_PROMPT

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


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


def _format_history_block(chat_history: list, n: int = 4) -> str:
    """Format the last N turns into a text block for the prompt."""
    if not chat_history:
        return ""
    recent = chat_history[-n:]
    lines = ["\n--- Conversation history (most recent first) ---"]
    for i, turn in enumerate(reversed(recent), 1):
        q = turn.get("question", "")
        a = str(turn.get("answer", "(no result)"))[:300]
        lines.append(f"Turn {i} — Q: {q}")
        lines.append(f"         A: {a}")
    lines.append("--- End of history ---\n")
    return "\n".join(lines)


def _extract_code(text: str) -> str:
    """Strip markdown fences from LLM response."""
    text = text.strip()
    m = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m[0].strip()
    m = re.findall(r"```\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m[0].strip()
    return text.strip()


def analyst_node(state: AgentState) -> dict:
    """LangGraph node: generate pandas code, execute, self-correct up to 3x."""
    question = state["question"]
    df_path = state["df_path"]
    chat_history = state.get("chat_history", [])

    # Load df
    try:
        df = pd.read_parquet(df_path)
    except Exception as exc:
        return {
            "analysis_result": None,
            "analysis_error": f"Failed to load data: {exc}",
            "pandas_code": "",
            "analyst_attempts": 0,
        }

    col_list = ", ".join(df.columns.tolist()[:20])
    dtype_info = ", ".join(f"{c}: {t}" for c, t in df.dtypes.astype(str).items())[:500]
    history_block = _format_history_block(chat_history)

    llm = _get_llm()
    if llm is None:
        # Fallback: just describe
        result = PandasTool.result_to_json(df.describe())
        return {
            "analysis_result": result,
            "analysis_error": None,
            "pandas_code": "result = df.describe()",
            "analyst_attempts": 0,
        }

    last_code = ""
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt == 1:
                prompt = ANALYST_PROMPT.format(
                    rows=len(df),
                    cols=len(df.columns),
                    col_list=col_list,
                    dtype_info=dtype_info,
                    history_block=history_block,
                    question=question,
                )
            else:
                logger.warning(
                    "Analyst attempt %d/%d — fixing: %s", attempt, MAX_RETRIES, last_error[:100]
                )
                prompt = ANALYST_FIX_PROMPT.format(
                    question=question,
                    col_list=col_list,
                    broken_code=last_code,
                    error_msg=last_error,
                )

            response = llm.invoke(prompt)
            last_code = _extract_code(response.content)

            success, result = PandasTool.execute_code(df, last_code)

            if success:
                logger.info("Analyst succeeded on attempt %d/%d", attempt, MAX_RETRIES)
                json_result = PandasTool.result_to_json(result)
                return {
                    "analysis_result": json_result,
                    "analysis_error": None,
                    "pandas_code": last_code,
                    "analyst_attempts": attempt,
                }
            else:
                last_error = str(result)

        except Exception as exc:
            last_error = str(exc)
            logger.warning("Analyst attempt %d/%d exception: %s", attempt, MAX_RETRIES, last_error)

    logger.error("Analyst: all %d attempts failed. Last error: %s", MAX_RETRIES, last_error)
    return {
        "analysis_result": None,
        "analysis_error": f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}",
        "pandas_code": last_code,
        "analyst_attempts": MAX_RETRIES,
    }
