"""Pandas data manipulation tools"""
import pandas as pd
import numpy as np
from typing import Any, Dict

class PandasTool:
    """Tool for pandas operations"""
    
    @staticmethod
    def execute_code(df: pd.DataFrame, code: str) -> tuple[bool, Any]:
        """
        Execute pandas code safely
        Returns: (success: bool, result: Any)
        """
        try:
            # Create a safe namespace
            namespace = {
                'df': df.copy(),
                'pd': pd,
                'np': np,
            }
            
            # Execute the code
            exec(code, namespace)
            
            # Get the result (last variable or df)
            if 'result' in namespace:
                return True, namespace['result']
            else:
                return True, namespace['df']
                
        except Exception as e:
            return False, f"Error executing code: {str(e)}"
    
    @staticmethod
    def get_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
        """Get summary statistics"""
        stats = {}
        
        # Numeric columns
        numeric_df = df.select_dtypes(include=[np.number])
        if not numeric_df.empty:
            stats['numeric'] = numeric_df.describe().to_dict()
        
        # Categorical columns
        categorical_df = df.select_dtypes(include=['object'])
        if not categorical_df.empty:
            stats['categorical'] = {
                col: df[col].value_counts().head(10).to_dict()
                for col in categorical_df.columns
            }
        
        return stats
    
    @staticmethod
    def detect_outliers(df: pd.DataFrame, column: str) -> pd.Series:
        """Detect outliers using IQR method"""
        if column not in df.columns:
            return pd.Series()
        
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        
        outliers = (df[column] < (Q1 - 1.5 * IQR)) | (df[column] > (Q3 + 1.5 * IQR))
        return df[outliers]
    
    @staticmethod
    def get_correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
        """Get correlation matrix for numeric columns"""
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return pd.DataFrame()
        
        return numeric_df.corr()