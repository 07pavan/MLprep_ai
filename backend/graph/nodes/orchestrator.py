"""Orchestrator node — classifies user intent via LLM with keyword fallback"""
from __future__ import annotations
import json
import logging

import pandas as pd
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from graph.state import AgentState
from utils.prompts import ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)


def _get_llm():
    """Create an LLM instance (Groq primary, Gemini backup)."""
    try:
        return ChatGroq(
            model=settings.PRIMARY_MODEL,
            temperature=0,
            groq_api_key=settings.GROQ_API_KEY,
        )
    except Exception:
        try:
            return ChatGoogleGenerativeAI(
                model=settings.BACKUP_MODEL,
                temperature=0,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        except Exception:
            return None


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

    # Load schema info for prompt
    try:
        df = pd.read_parquet(df_path)
        rows, cols = len(df), len(df.columns)
        col_list = ", ".join(df.columns.tolist()[:20])
        dtype_info = ", ".join(f"{c}: {t}" for c, t in df.dtypes.astype(str).items())[:400]
    except Exception:
        rows, cols, col_list, dtype_info = 0, 0, "", ""

    intent = _keyword_classify(question)  # default fallback

    llm = _get_llm()
    if llm is not None:
        try:
            prompt = ORCHESTRATOR_PROMPT.format(
                rows=rows,
                cols=cols,
                col_list=col_list,
                dtype_info=dtype_info,
                question=question,
            )
            response = llm.invoke(prompt)
            text = response.content.strip()

            # Parse JSON response
            parsed = None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Try to extract JSON from text
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    try:
                        parsed = json.loads(text[start : end + 1])
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
                    logger.info(
                        "Orchestrator LLM classified intent='%s' reason='%s'",
                        intent,
                        parsed.get("reasoning", ""),
                    )

        except Exception as exc:
            logger.warning("Orchestrator LLM failed (%s), using keyword fallback", exc)

    logger.info("Orchestrator final intent: %s for question: %s", intent, question[:80])
    return {"intent": intent}
