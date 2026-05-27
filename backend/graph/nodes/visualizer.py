"""Visualizer node — generates Vega-Lite specs via rules, LLM, or failsafe"""
from __future__ import annotations
import logging

import pandas as pd
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from graph.state import AgentState
from tools.vegalite_tool import VegaLiteTool
from utils.prompts import VEGALITE_PROMPT, VEGALITE_FIX_PROMPT

logger = logging.getLogger(__name__)

VIZ_MAX_RETRIES = 3
vegalite_tool = VegaLiteTool()


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


def visualizer_node(state: AgentState) -> dict:
    """LangGraph node: 3-tier Vega-Lite spec generation."""
    question = state["question"]
    df_path = state["df_path"]
    analysis_result = state.get("analysis_result")

    # Load df
    try:
        df = pd.read_parquet(df_path)
    except Exception as exc:
        return {
            "vega_spec": None,
            "viz_source": "none",
            "viz_attempts": 0,
            "error": f"Failed to load data for visualization: {exc}",
        }

    # Prepare data records for embedding in specs
    if isinstance(analysis_result, list) and len(analysis_result) > 0:
        data_records = analysis_result[:200]
    else:
        data_records = df.head(200).to_dict(orient="records")

    # ── Tier 1: Rule-based ────────────────────────────────────────
    try:
        spec = vegalite_tool.generate_spec_from_rules(df, question, data_records)
        if spec is not None:
            valid, msg = vegalite_tool.validate_spec(spec)
            if valid:
                logger.info("Visualizer: rule-based spec generated.")
                return {
                    "vega_spec": spec,
                    "viz_source": "auto",
                    "viz_attempts": 0,
                }
    except Exception as exc:
        logger.warning("Visualizer: rule engine raised %s", exc)

    # ── Tier 2: LLM-powered ──────────────────────────────────────
    llm = _get_llm()
    if llm is not None:
        col_list = ", ".join(df.columns.tolist()[:20])
        dtype_info = ", ".join(f"{c}: {t}" for c, t in df.dtypes.astype(str).items())[:400]
        sample_data = str(df.head(3).to_dict(orient="records"))[:300]

        analysis_sample = ""
        if isinstance(analysis_result, list):
            analysis_sample = str(analysis_result[:3])[:300]
        elif analysis_result is not None:
            analysis_sample = str(analysis_result)[:300]

        last_spec_str = ""
        last_error = ""

        for attempt in range(1, VIZ_MAX_RETRIES + 1):
            try:
                if attempt == 1:
                    prompt = VEGALITE_PROMPT.format(
                        rows=len(df),
                        cols=len(df.columns),
                        col_list=col_list,
                        dtype_info=dtype_info,
                        sample_data=sample_data,
                        analysis_result_sample=analysis_sample,
                        question=question,
                    )
                else:
                    logger.warning(
                        "Visualizer attempt %d/%d — fixing: %s",
                        attempt, VIZ_MAX_RETRIES, last_error[:100],
                    )
                    prompt = VEGALITE_FIX_PROMPT.format(
                        question=question,
                        col_list=col_list,
                        broken_spec=last_spec_str,
                        error_msg=last_error,
                    )

                response = llm.invoke(prompt)
                raw = response.content
                spec = vegalite_tool.extract_json(raw)

                if spec is None:
                    last_spec_str = raw[:500]
                    last_error = "Could not parse JSON from LLM response"
                    continue

                last_spec_str = str(spec)[:500]

                # Ensure $schema
                if "$schema" not in spec:
                    spec["$schema"] = VegaLiteTool.SCHEMA
                if "width" not in spec:
                    spec["width"] = "container"
                if "height" not in spec:
                    spec["height"] = 350

                valid, msg = vegalite_tool.validate_spec(spec)
                if valid:
                    # Inject data
                    spec["data"] = {"values": data_records}
                    logger.info(
                        "Visualizer: LLM spec succeeded on attempt %d/%d",
                        attempt, VIZ_MAX_RETRIES,
                    )
                    return {
                        "vega_spec": spec,
                        "viz_source": "llm",
                        "viz_attempts": attempt,
                    }
                else:
                    last_error = msg

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Visualizer attempt %d/%d exception: %s",
                    attempt, VIZ_MAX_RETRIES, last_error,
                )

    # ── Tier 3: Failsafe ──────────────────────────────────────────
    logger.warning("Visualizer: falling back to failsafe spec.")
    fallback = vegalite_tool.build_fallback_spec(df, data_records)
    return {
        "vega_spec": fallback,
        "viz_source": "failsafe",
        "viz_attempts": 0,
    }
