"""Visualization tools using Plotly"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Any

class ChartTool:
    """Tool for creating visualizations"""
    
    @staticmethod
    def execute_viz_code(df: pd.DataFrame, code: str) -> tuple[bool, Any]:
        """
        Execute plotly visualization code
        Returns: (success: bool, figure: plotly.graph_objects.Figure)
        """
        try:
            namespace = {
                'df': df.copy(),
                'px': px,
                'go': go,
                'pd': pd,
            }
            
            exec(code, namespace)
            
            # Look for 'fig' variable
            if 'fig' in namespace:
                return True, namespace['fig']
            else:
                return False, "No 'fig' variable found in code"
                
        except Exception as e:
            return False, f"Error creating visualization: {str(e)}"
    
    @staticmethod
    def auto_chart(df: pd.DataFrame, x_col: str = None, y_col: str = None, chart_type: str = "auto"):
        """Automatically create appropriate chart"""
        
        if chart_type == "auto":
            # Determine best chart type
            if x_col and y_col:
                x_type = df[x_col].dtype
                y_type = df[y_col].dtype
                
                if pd.api.types.is_numeric_dtype(y_type):
                    if pd.api.types.is_datetime64_any_dtype(x_type):
                        chart_type = "line"
                    elif df[x_col].nunique() < 20:
                        chart_type = "bar"
                    else:
                        chart_type = "scatter"
        
        # Create chart based on type
        if chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col)
        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col)
        elif chart_type == "histogram":
            fig = px.histogram(df, x=x_col)
        elif chart_type == "box":
            fig = px.box(df, y=y_col)
        else:
            fig = px.bar(df, x=x_col, y=y_col)
        
        return fig