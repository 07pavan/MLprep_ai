"""LangGraph shared state definition"""
from __future__ import annotations
from typing import TypedDict, Optional, Any


class AgentState(TypedDict):
    """The state dict that flows through every LangGraph node."""
    session_id: str
    question: str
    chat_history: list           # list[{question, answer}]
    df_path: str                 # path to session's Parquet file
    trace_id: str                # observability correlation ID

    # Orchestrator output
    intent: str                  # analysis_only | analysis_and_visualization | insights | cleaning_report
    force_intent: str            # if non-empty, orchestrator skips LLM and uses this directly

    # Analyst output
    pandas_code: str
    analysis_result: Any         # JSON-serializable (list[dict] | dict | scalar)
    analysis_error: Optional[str]
    analyst_attempts: int

    # Visualizer output
    vega_spec: Optional[dict]
    viz_source: str              # "auto" | "llm" | "failsafe"
    viz_attempts: int

    # Insights output
    insights: str
    suggested_questions: list       # 3 contextual follow-up questions

    # Persona & context
    persona: str                    # "general" | "finance" | "marketing" | "engineering"

    # Clarification
    clarification_needed: bool      # True if orchestrator detects ambiguity
    clarification_question: str     # The clarifying question to show the user

    # Profiling output
    profiling_result: Optional[dict]

    # Quality output
    quality_result: Optional[dict]

    # ML Readiness output
    ml_readiness_result: Optional[dict]

    # Cleaning plan output
    cleaning_plan: Optional[dict]

    # General
    error: Optional[str]

