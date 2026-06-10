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

# Global reference for PostgreSQL connection pool
db_pool = None


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

    # Compile with dynamic checkpointer (PostgresSaver if DATABASE_URL is set, FirestoreSaver if FIREBASE_PROJECT_ID is set, otherwise MemorySaver)
    from config.settings import settings
    if settings.DATABASE_URL:
        try:
            logger.info("🔌 Initializing PostgreSQL checkpointer state store...")
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
            from langgraph.checkpoint.postgres import PostgresSaver

            global db_pool
            db_pool = ConnectionPool(
                conninfo=settings.DATABASE_URL,
                max_size=10,
                kwargs={"autocommit": True, "row_factory": dict_row}
            )
            # Create the schema tables in the Postgres database if they do not exist
            checkpointer = PostgresSaver(db_pool)
            checkpointer.setup()
            
            compiled = builder.compile(checkpointer=checkpointer)
            logger.info("🚀 LangGraph compiled successfully with PostgresSaver checkpointer.")
        except Exception as e:
            logger.error("❌ Failed to setup Postgres checkpointer: %s. Falling back to MemorySaver.", str(e))
            memory = MemorySaver()
            compiled = builder.compile(checkpointer=memory)
    elif settings.FIREBASE_PROJECT_ID:
        try:
            logger.info("🔌 Initializing Firestore checkpointer state store for project %s...", settings.FIREBASE_PROJECT_ID)
            
            # Setup environment variable for google library credentials if provided
            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
            
            # Set Google Cloud Project ID explicitly
            import os
            os.environ["GOOGLE_CLOUD_PROJECT"] = settings.FIREBASE_PROJECT_ID
                
            from langgraph.checkpoint.firestore import FirestoreSaver
            checkpointer = FirestoreSaver()
            compiled = builder.compile(checkpointer=checkpointer)
            logger.info("🚀 LangGraph compiled successfully with FirestoreSaver checkpointer.")
        except Exception as e:
            logger.error("❌ Failed to setup Firestore checkpointer: %s. Falling back to MemorySaver.", str(e))
            memory = MemorySaver()
            compiled = builder.compile(checkpointer=memory)
    else:
        logger.info("ℹ️ DATABASE_URL and FIREBASE_PROJECT_ID not set. Compiling LangGraph with local in-memory MemorySaver.")
        memory = MemorySaver()
        compiled = builder.compile(checkpointer=memory)

    return compiled


# Singleton compiled graph
app_graph = build_graph()
