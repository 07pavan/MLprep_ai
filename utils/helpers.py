"""Helper utilities"""
import pandas as pd
import numpy as np
from typing import Dict, Any

def get_dataset_info(df: pd.DataFrame) -> Dict[str, Any]:
    """Get comprehensive dataset information"""
    info = {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "memory_usage_mb": df.memory_usage(deep=True).sum() / (1024 * 1024),
    }
    
    # Numeric columns stats
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        info["numeric_columns"] = numeric_cols
        info["numeric_stats"] = df[numeric_cols].describe().to_dict()
    
    # Categorical columns
    categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
    if categorical_cols:
        info["categorical_columns"] = categorical_cols
        info["categorical_stats"] = {
            col: {
                "unique_values": df[col].nunique(),
                "top_values": df[col].value_counts().head(5).to_dict()
            }
            for col in categorical_cols
        }
    
    # Date columns
    date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
    if date_cols:
        info["date_columns"] = date_cols
    
    return info

def get_column_schema(df: pd.DataFrame) -> str:
    """Get formatted schema for LLM"""
    schema = "Dataset Schema:\n"
    schema += f"Total Rows: {len(df)}\n"
    schema += f"Total Columns: {len(df.columns)}\n\n"
    
    for col in df.columns:
        dtype = df[col].dtype
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100
        
        schema += f"- {col}: {dtype}"
        if null_count > 0:
            schema += f" ({null_pct:.1f}% missing)"
        
        # Add sample values for categorical
        if dtype == 'object' and df[col].nunique() < 20:
            unique_vals = df[col].dropna().unique()[:5]
            schema += f" | Examples: {', '.join(map(str, unique_vals))}"
        
        schema += "\n"
    
    return schema

def format_analysis_result(result: Any) -> str:
    """Format analysis result for display"""
    if isinstance(result, pd.DataFrame):
        return result.to_string()
    elif isinstance(result, pd.Series):
        return result.to_string()
    elif isinstance(result, (int, float)):
        return f"{result:,.2f}" if isinstance(result, float) else f"{result:,}"
    else:
        return str(result)