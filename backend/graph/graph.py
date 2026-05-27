"""LangGraph StateGraph — the compiled execution graph for the data analyst pipeline"""
from __future__ import annotations
import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import AgentState
from graph.nodes.orchestrator import orchestrator_node
from graph.nodes.analyst import analyst_node
from graph.nodes.visualizer import visualizer_node
from graph.nodes.insights import insights_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------

def route_after_orchestrator(state: AgentState) -> str:
    """Always run the analyst first (every question needs data work)."""
    intent = state.get("intent", "analysis_only")
    if intent == "cleaning_report":
        return END   # cleaning is handled by a dedicated router, not the graph
    return "analyst"


def route_after_analyst(state: AgentState) -> str:
    """After analysis, decide whether to visualize or generate insights."""
    intent = state.get("intent", "analysis_only")
    if intent == "analysis_and_visualization":
        return "visualizer"
    if intent == "insights":
        return "insights_generator"
    return END


def route_after_visualizer(state: AgentState) -> str:
    return END


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph():
    """Construct and compile the LangGraph."""
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("visualizer", visualizer_node)
    builder.add_node("insights_generator", insights_node)

    # Entry point
    builder.set_entry_point("orchestrator")

    # Conditional edges
    builder.add_conditional_edges("orchestrator", route_after_orchestrator)
    builder.add_conditional_edges("analyst", route_after_analyst)
    builder.add_conditional_edges("visualizer", route_after_visualizer)
    builder.add_edge("insights_generator", END)

    # Compile with memory checkpointer (enables cross-turn state)
    memory = MemorySaver()
    compiled = builder.compile(checkpointer=memory)

    logger.info("LangGraph compiled successfully.")
    return compiled


# Singleton compiled graph
app_graph = build_graph()
