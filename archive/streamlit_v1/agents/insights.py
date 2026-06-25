"""Insights Generator Agent - Discovers patterns and generates insights"""
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from tools import StatsTool
import pandas as pd
from typing import Dict, Any, List

class InsightsAgent:
    """Agent that generates insights from data"""
    
    def __init__(self):
        try:
            self.llm = ChatGroq(
                model=settings.PRIMARY_MODEL,
                temperature=0.3,
                groq_api_key=settings.GROQ_API_KEY
            )
        except Exception as e:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.BACKUP_MODEL,
                    temperature=0.3,
                    google_api_key=settings.GOOGLE_API_KEY
                )
            except:
                self.llm = None
        
        self.stats_tool = StatsTool()
    
    def generate_insights(self, df: pd.DataFrame, question: str, analysis_result: Any) -> Dict[str, Any]:
        """Generate insights from analysis results"""
        
        if self.llm is None:
            return self._simple_insights(df, question, analysis_result)
        
        # Create prompt
        result_str = str(analysis_result)[:500] if analysis_result is not None else "No result"
        
        prompt = f"""Analyze this data and provide 3-5 key insights.

Question: {question}
Analysis Result: {result_str}
Dataset size: {len(df)} rows

Provide specific, data-driven insights in bullet points."""

        try:
            response = self.llm.invoke(prompt)
            return {
                "success": True,
                "insights": response.content,
                "raw_response": response.content
            }
        except Exception as e:
            print(f"Insights generation error: {e}")
            return self._simple_insights(df, question, analysis_result)
    
    def _simple_insights(self, df: pd.DataFrame, question: str, analysis_result: Any) -> Dict[str, Any]:
        """Generate simple insights without LLM"""
        insights = []
        
        insights.append(f"✓ Dataset contains {len(df):,} rows and {len(df.columns)} columns")
        
        if isinstance(analysis_result, (int, float)):
            insights.append(f"✓ Calculated value: {analysis_result:,.2f}")
        elif isinstance(analysis_result, pd.DataFrame):
            insights.append(f"✓ Analysis produced {len(analysis_result)} result rows")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            insights.append(f"✓ Dataset has {len(numeric_cols)} numeric columns for analysis")
        
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        if categorical_cols:
            insights.append(f"✓ Dataset has {len(categorical_cols)} categorical columns")
        
        insights_text = "\n".join(insights)
        
        return {
            "success": True,
            "insights": insights_text,
            "raw_response": insights_text
        }
    
    def auto_discover_patterns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Automatically discover interesting patterns in data"""
        patterns = []
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        # Analyze numeric columns
        for col in numeric_cols[:5]:
            try:
                dist_analysis = self.stats_tool.distribution_analysis(df, col)
                if dist_analysis and "error" not in dist_analysis:
                    patterns.append({
                        "type": "distribution",
                        "column": col,
                        "details": dist_analysis
                    })
            except Exception as e:
                print(f"Error analyzing {col}: {e}")
        
        # Correlations
        if len(numeric_cols) >= 2:
            for i, col1 in enumerate(numeric_cols[:3]):
                for col2 in numeric_cols[i+1:4]:
                    try:
                        corr = self.stats_tool.correlation_analysis(df, col1, col2)
                        if corr and "error" not in corr:
                            if abs(corr.get("correlation", 0)) > 0.5:
                                patterns.append({
                                    "type": "correlation",
                                    "columns": [col1, col2],
                                    "details": corr
                                })
                    except Exception as e:
                        print(f"Error correlating {col1} and {col2}: {e}")
        
        return patterns
    
    def summarize_patterns(self, patterns: List[Dict[str, Any]]) -> str:
        """Generate natural language summary of patterns"""
        if not patterns:
            return "No significant patterns detected."
        
        summary_parts = ["🔍 **Discovered Patterns:**\n"]
        
        for i, pattern in enumerate(patterns[:10], 1):
            if pattern["type"] == "correlation":
                corr_val = pattern["details"].get("correlation", 0)
                strength = pattern["details"].get("strength", "unknown")
                summary_parts.append(
                    f"{i}. **Correlation**: {pattern['columns'][0]} and {pattern['columns'][1]} "
                    f"have {strength} correlation ({corr_val:.3f})"
                )
            
            elif pattern["type"] == "distribution":
                mean = pattern["details"].get("mean", 0)
                std = pattern["details"].get("std", 0)
                summary_parts.append(
                    f"{i}. **Distribution**: {pattern['column']} has mean={mean:.2f}, std={std:.2f}"
                )
        
        return "\n".join(summary_parts)