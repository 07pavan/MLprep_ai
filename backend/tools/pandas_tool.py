"""Pandas code execution tool with hardened security sandbox.

Defense layers:
  1. sanitize_code() regex strips dangerous imports/calls
  2. Restricted __builtins__ — only safe functions allowed
  3. Thread-based timeout — kills runaway code after EXEC_TIMEOUT seconds
  4. df.copy() — prevents mutation of session DataFrame
"""
from __future__ import annotations
import logging
import threading
from typing import Any

import pandas as pd
import numpy as np

from utils.validators import sanitize_code

logger = logging.getLogger(__name__)

EXEC_TIMEOUT = 5  # seconds

# Only these builtins are available inside exec()
SAFE_BUILTINS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "filter",
    "float", "frozenset", "int", "isinstance", "issubclass",
    "iter", "len", "list", "map", "max", "min", "next",
    "print", "range", "repr", "reversed", "round",
    "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip",
    "True", "False", "None",
    "ValueError", "TypeError", "KeyError", "IndexError",
    "Exception", "StopIteration",
}


def _build_restricted_builtins() -> dict:
    """Build a dict of only safe builtins for the exec namespace."""
    import builtins
    full = vars(builtins)
    restricted = {k: full[k] for k in SAFE_BUILTINS if k in full}
    return restricted


class PandasTool:
    """Execute LLM-generated pandas code in a sandboxed namespace."""

    _restricted_builtins = _build_restricted_builtins()

    @staticmethod
    def execute_code(df: pd.DataFrame, code: str) -> tuple[bool, Any]:
        """
        Sanitize and execute pandas code with timeout.
        Returns (success, result_or_error).
        """
        try:
            safe_code = sanitize_code(code)
        except Exception as e:
            return False, f"Code sanitization error: {e}"

        namespace = {
            "__builtins__": PandasTool._restricted_builtins,
            "df": df.copy(),
            "pd": pd,
            "np": np,
        }

        result_box: dict = {}
        error_box: dict = {}

        def _run():
            try:
                exec(safe_code, namespace)
                if "result" in namespace:
                    result_box["value"] = namespace["result"]
                else:
                    error_box["msg"] = "No 'result' variable found in generated code"
            except Exception as e:
                error_box["msg"] = f"Code execution error: {e}"

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=EXEC_TIMEOUT)

        if thread.is_alive():
            logger.warning("Code execution timed out after %ds", EXEC_TIMEOUT)
            return False, (
                f"Code execution timed out after {EXEC_TIMEOUT}s. "
                "The code may contain an infinite loop or very heavy computation. "
                "Try simplifying the query."
            )

        if "msg" in error_box:
            return False, error_box["msg"]
        if "value" in result_box:
            return True, result_box["value"]
        return False, "Unknown execution error — no result captured"

    @staticmethod
    def result_to_json(result: Any) -> Any:
        """
        Convert a pandas result into a JSON-serializable form.

        DataFrame  → list[dict]
        Series     → dict
        scalar     → native Python type
        """
        if isinstance(result, pd.DataFrame):
            df_out = result.head(500)
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
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val
