import pandas as pd
import numpy as np
from typing import Any, Tuple, Optional, Dict

class ResponseFormatter:
    """Formats the raw result of a copilot query into a serializable API response.
    
    Enforces a maximum row limit of 500 and provides truncation metadata.
    """
    
    @staticmethod
    def format_result(
        success: bool,
        result: Any,
        executed_code: str,
        error_msg: Optional[str],
        execution_type: str,
        execution_time_ms: int,
        debug_mode: bool = False
    ) -> Dict[str, Any]:
        """Builds a structured API response dictionary."""
        if not success:
            return {
                "success": False,
                "answer": f"An error occurred while answering your question: {error_msg}",
                "data": None,
                "truncation_meta": None,
                "code": executed_code if debug_mode else None,
                "error": error_msg,
                "execution_type": execution_type,
                "execution_time_ms": execution_time_ms
            }
            
        # Helper to make values serializable and apply limit
        serializable_data, truncation_meta = ResponseFormatter._serialize_value(result)
        
        # Build textual answer
        if isinstance(result, (int, float, str, np.number)):
            answer = f"The result is {result}."
        elif isinstance(result, pd.DataFrame):
            answer = f"Found {len(result)} records matching your query."
        elif isinstance(result, dict):
            answer = "Here is the summary."
        else:
            answer = "Here are the query results."
            
        response = {
            "success": True,
            "answer": answer,
            "data": serializable_data,
            "truncation_meta": truncation_meta,
            "execution_type": execution_type,
            "execution_time_ms": execution_time_ms
        }
        
        if debug_mode:
            response["code"] = executed_code
            
        return response

    @staticmethod
    def _serialize_value(val: Any) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Convert numpy/pandas types and collection values to serializable types.
        
        Enforces maximum 500 rows limit on DataFrames.
        """
        if isinstance(val, pd.DataFrame):
            total_rows = len(val)
            limit = 500
            df_out = val.head(limit)
            
            # Avoid datetime warnings by converting them to str
            for col in df_out.select_dtypes(include=["datetime64"]).columns:
                df_out[col] = df_out[col].astype(str)
                
            records = df_out.to_dict(orient="records")
            
            truncation_meta = None
            if total_rows > limit:
                truncation_meta = {
                    "truncated": True,
                    "total_rows": total_rows,
                    "returned_rows": len(records)
                  }
                  
            return records, truncation_meta

        if isinstance(val, pd.Series):
            s = val.head(200)
            records = {str(k): ResponseFormatter._serialize_val_recursive(v) for k, v in s.items()}
            return records, None

        # Otherwise handle generic values recursively
        return ResponseFormatter._serialize_val_recursive(val), None

    @staticmethod
    def _serialize_val_recursive(val: Any) -> Any:
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        if isinstance(val, np.ndarray):
            return [ResponseFormatter._serialize_val_recursive(x) for x in val.tolist()]
        if isinstance(val, pd.Timestamp):
            return val.isoformat()
        if isinstance(val, list):
            return [ResponseFormatter._serialize_val_recursive(x) for x in val]
        if isinstance(val, tuple):
            return [ResponseFormatter._serialize_val_recursive(x) for x in val]
        if isinstance(val, set):
            return [ResponseFormatter._serialize_val_recursive(x) for x in val]
        if isinstance(val, dict):
            return {str(k): ResponseFormatter._serialize_val_recursive(v) for k, v in val.items()}
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        return val
