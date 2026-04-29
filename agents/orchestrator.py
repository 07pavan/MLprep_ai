"""Orchestrator Agent - Coordinates all other agents"""
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
import pandas as pd
from typing import Dict, Any

class OrchestratorAgent:
    """Main agent that coordinates all other agents"""
    
    def __init__(self):
        try:
            self.llm = ChatGroq(
                model=settings.PRIMARY_MODEL,
                temperature=settings.TEMPERATURE,
                groq_api_key=settings.GROQ_API_KEY
            )
        except Exception as e:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.BACKUP_MODEL,
                    temperature=settings.TEMPERATURE,
                    google_api_key=settings.GOOGLE_API_KEY
                )
            except:
                self.llm = None
    
    def plan_execution(self, question: str, dataset_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create execution plan for answering the question"""
        plan = self._create_simple_plan(question)
        
        return {
            "success": True,
            "plan": plan,
            "raw_response": "Simple routing plan"
        }
    
    def _create_simple_plan(self, question: str) -> Dict[str, Any]:
        """Create a simple execution plan based on keywords"""
        question_lower = question.lower()
        agents = []
        
        # Determine which agents to use
        if any(word in question_lower for word in ["show", "display", "chart", "plot", "graph", "visualize", "trend"]):
            agents = ["analyst", "visualizer"]
        elif any(word in question_lower for word in ["insight", "pattern", "discover", "find", "unusual", "anomaly"]):
            agents = ["analyst", "insights"]
        elif any(word in question_lower for word in ["profile", "describe", "summary", "overview"]):
            agents = ["data_profiler"]
        else:
            agents = ["analyst"]
        
        return {
            "agents": agents,
            "reasoning": f"Keyword-based routing for: {question}",
            "complexity": "simple" if len(agents) == 1 else "medium"
        }