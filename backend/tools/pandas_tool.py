"""Pandas code execution tool with security sandbox"""
from __future__ import annotations
import logging
from typing import Any

import pandas as pd
import numpy as np

from utils.validators import sanitize_code

logger = logging.getLogger(__name__)


class PandasTool:
    """Execute LLM-generated pandas code in a sandboxed namespace."""

    @staticmethod
    def execute_code(df: pd.DataFrame, code: str) -> tuple[bool, Any]:
        """
        Sanitize and execute pandas code.
        Returns (success, result_or_error).
        """
        try:
            safe_code = sanitize_code(code)
            namespace = {
                "df": df.copy(),
                "pd": pd,
                "np": np,
            }
            exec(safe_code, namespace)

            if "result" in namespace:
                return True, namespace["result"]
            else:
                return False, "No 'result' variable found in generated code"
        except Exception as e:
            return False, f"Code execution error: {str(e)}"

    @staticmethod
    def result_to_json(result: Any) -> Any:
        """
        Convert a pandas result into a JSON-serializable form.

        DataFrame  → list[dict]
        Series     → dict
        scalar     → native Python type
        """
        if isinstance(result, pd.DataFrame):
            # Cap at 500 rows for API transport
            df_out = result.head(500)
            # Convert timestamps to ISO strings
            for col in df_out.select_dtypes(include=["datetime64"]).columns:
                df_out[col] = df_out[col].astype(str)
            return df_out.to_dict(orient="records")

        if isinstance(result, pd.Series):
            s = result.head(200)
            return {str(k): _make_serializable(v) for k, v in s.items()}

        return _make_serializable(result)


def _make_serializable(val: Any) -> Any:
    """Convert numpy/pandas scalars to native Python types."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    if pd.isna(val):
        return None
    return val
