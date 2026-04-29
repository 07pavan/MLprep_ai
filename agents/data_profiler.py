"""Data Profiler Agent - Analyzes uploaded CSV files"""
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from utils import get_dataset_info, get_column_schema
import pandas as pd
from typing import Dict, Any

class DataProfilerAgent:
    """Agent that profiles and analyzes datasets"""
    
    def __init__(self):
        try:
            self.llm = ChatGroq(
                model=settings.PRIMARY_MODEL,
                temperature=settings.TEMPERATURE,
                groq_api_key=settings.GROQ_API_KEY
            )
        except Exception as e:
            print(f"Error initializing Groq: {e}")
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.BACKUP_MODEL,
                    temperature=settings.TEMPERATURE,
                    google_api_key=settings.GOOGLE_API_KEY
                )
            except Exception as e2:
                print(f"Error initializing Gemini: {e2}")
                self.llm = None
    
    def profile_dataset(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Profile the uploaded dataset"""
        dataset_info = get_dataset_info(df)
        schema = get_column_schema(df)
        
        profile = {
            "basic_info": {
                "rows": dataset_info["rows"],
                "columns": dataset_info["columns"],
                "memory_mb": round(dataset_info["memory_usage_mb"], 2),
            },
            "column_info": {
                "names": dataset_info["column_names"],
                "types": dataset_info["dtypes"],
                "missing": dataset_info["missing_values"],
            },
            "schema": schema,
            "llm_analysis": "Dataset profiled successfully",
            "raw_info": dataset_info
        }
        
        if "numeric_columns" in dataset_info:
            profile["numeric_columns"] = dataset_info["numeric_columns"]
        if "categorical_columns" in dataset_info:
            profile["categorical_columns"] = dataset_info["categorical_columns"]
        if "date_columns" in dataset_info:
            profile["date_columns"] = dataset_info["date_columns"]
        
        return profile
    
    def get_data_quality_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate data quality report"""
        total_cells = len(df) * len(df.columns)
        filled_cells = total_cells - df.isnull().sum().sum()
        
        report = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "duplicate_rows": int(df.duplicated().sum()),
            "completeness_score": round((filled_cells / total_cells) * 100, 2) if total_cells > 0 else 0
        }
        
        return report
    
    def suggest_questions(self, df: pd.DataFrame) -> list:
        """Suggest interesting questions based on data structure"""
        suggestions = []
        
        # Basic questions
        suggestions.append("Show me the first 10 rows")
        suggestions.append("What is the summary of this dataset?")
        suggestions.append(f"How many rows are in this dataset?")
        
        # Numeric column questions
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            col = numeric_cols[0]
            suggestions.append(f"What is the average {col}?")
            suggestions.append(f"What is the total {col}?")
            
            if len(numeric_cols) > 1:
                col2 = numeric_cols[1]
                suggestions.append(f"Show me the correlation between {col} and {col2}")
        
        # Categorical questions
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        if categorical_cols:
            col = categorical_cols[0]
            suggestions.append(f"Show me the distribution of {col}")
        
        # Advanced
        suggestions.append("Find any unusual patterns in the data")
        
        return suggestions[:8]