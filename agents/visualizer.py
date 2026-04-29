"""Visualizer Agent - Creates charts and visualizations"""
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from config import settings
from utils import VISUALIZER_PROMPT, extract_code_from_response, sanitize_code
from tools import ChartTool
import pandas as pd
from typing import Dict, Any, Optional
import plotly.graph_objects as go

class VisualizerAgent:
    """Agent that creates visualizations"""
    
    def __init__(self):
        self.llm = ChatGroq(
            model=settings.PRIMARY_MODEL,
            temperature=settings.TEMPERATURE,
            groq_api_key=settings.GROQ_API_KEY
        )
        self.chart_tool = ChartTool()
    
    def create_visualization(self, df: pd.DataFrame, question: str, analysis_result: Any = None) -> Dict[str, Any]:
        """
        Create visualization based on question and data
        """
        # Prepare data summary
        data_summary = {
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "shape": df.shape,
            "sample": df.head(3).to_dict()
        }
        
        if analysis_result is not None:
            data_summary["analysis_result"] = str(analysis_result)
        
        # Generate visualization code using LLM
        prompt = ChatPromptTemplate.from_template(VISUALIZER_PROMPT)
        chain = prompt | self.llm
        
        try:
            response = chain.invoke({
                "data_summary": str(data_summary),
                "question": question
            })
            
            # Extract and sanitize code
            raw_code = extract_code_from_response(response.content)
            safe_code = sanitize_code(raw_code)
            
            # Execute visualization code
            success, fig = self.chart_tool.execute_viz_code(df, safe_code)
            
            return {
                "success": success,
                "figure": fig if success else None,
                "code": safe_code,
                "error": None if success else fig
            }
            
        except Exception as e:
            return {
                "success": False,
                "figure": None,
                "code": "",
                "error": str(e)
            }
    
    def create_auto_chart(self, df: pd.DataFrame, chart_type: str = "auto") -> Optional[go.Figure]:
        """Create automatic chart based on data structure"""
        try:
            # Determine columns to use
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
            date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
            
            x_col = None
            y_col = None
            
            # Simple logic for auto chart
            if date_cols and numeric_cols:
                x_col = date_cols[0]
                y_col = numeric_cols[0]
                chart_type = "line"
            elif categorical_cols and numeric_cols:
                x_col = categorical_cols[0]
                y_col = numeric_cols[0]
                chart_type = "bar"
            elif len(numeric_cols) >= 2:
                x_col = numeric_cols[0]
                y_col = numeric_cols[1]
                chart_type = "scatter"
            elif len(numeric_cols) == 1:
                y_col = numeric_cols[0]
                chart_type = "histogram"
            
            if x_col or y_col:
                return self.chart_tool.auto_chart(df, x_col, y_col, chart_type)
            
            return None
            
        except Exception as e:
            print(f"Error creating auto chart: {e}")
            return None