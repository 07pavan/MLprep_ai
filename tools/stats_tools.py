"""Statistical analysis tools"""
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Any

class StatsTool:
    """Tool for statistical operations"""
    
    @staticmethod
    def correlation_analysis(df: pd.DataFrame, col1: str, col2: str) -> Dict[str, Any]:
        """Calculate correlation between two columns"""
        try:
            corr_coefficient, p_value = stats.pearsonr(df[col1].dropna(), df[col2].dropna())
            
            return {
                "correlation": corr_coefficient,
                "p_value": p_value,
                "significant": p_value < 0.05,
                "strength": StatsTool._interpret_correlation(corr_coefficient)
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _interpret_correlation(corr: float) -> str:
        """Interpret correlation strength"""
        abs_corr = abs(corr)
        if abs_corr < 0.3:
            return "weak"
        elif abs_corr < 0.7:
            return "moderate"
        else:
            return "strong"
    
    @staticmethod
    def trend_analysis(df: pd.DataFrame, date_col: str, value_col: str) -> Dict[str, Any]:
        """Analyze trend in time series data"""
        try:
            df_sorted = df.sort_values(date_col)
            values = df_sorted[value_col].values
            
            # Simple linear regression
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)
            
            trend = "increasing" if slope > 0 else "decreasing"
            
            return {
                "trend": trend,
                "slope": slope,
                "start_value": values[0],
                "end_value": values[-1],
                "change_percent": ((values[-1] - values[0]) / values[0]) * 100
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def distribution_analysis(df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """Analyze distribution of a column"""
        try:
            data = df[column].dropna()
            
            return {
                "mean": data.mean(),
                "median": data.median(),
                "std": data.std(),
                "skewness": stats.skew(data),
                "kurtosis": stats.kurtosis(data),
                "min": data.min(),
                "max": data.max(),
                "q25": data.quantile(0.25),
                "q75": data.quantile(0.75),
            }
        except Exception as e:
            return {"error": str(e)}