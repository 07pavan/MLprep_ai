from __future__ import annotations
import re
from typing import Any
import pandas as pd

def generate_cleaning_plan(df: pd.DataFrame, quality_report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Generate a deterministic data cleaning plan from quality scan issues.

    Args:
        df: The pandas DataFrame to inspect.
        quality_report: The dictionary returned by the check_quality tool.

    Returns:
        A dictionary containing a list of planned steps:
        {
            "steps": [
                {
                    "issue": "missing_values" | "duplicate_rows" | "outliers" | "high_cardinality" | "type_mismatch",
                    "column": str | None,
                    "action": str,
                    "reason": str
                }
            ]
        }
    """
    steps = []
    issues = quality_report.get("issues", [])

    # Map outlier columns for context
    outlier_cols = {issue["column"] for issue in issues if issue["type"] == "outliers"}

    for issue in issues:
        itype = issue["type"]
        col = issue["column"]
        details = issue["details"]

        if itype == "missing_values":
            if col in df.columns:
                is_numeric = pd.api.types.is_numeric_dtype(df[col])
                if is_numeric:
                    # Choose median if column has outlier issues, else mean
                    action = "median_imputation" if col in outlier_cols else "mean_imputation"
                    reason = f"Numerical column '{col}' has {details}"
                else:
                    action = "mode_imputation"
                    reason = f"Categorical column '{col}' has {details}"
                
                steps.append({
                    "issue": itype,
                    "column": col,
                    "action": action,
                    "reason": reason
                })

        elif itype == "duplicate_rows":
            steps.append({
                "issue": itype,
                "column": None,
                "action": "remove_duplicates",
                "reason": details
            })

        elif itype == "outliers":
            steps.append({
                "issue": itype,
                "column": col,
                "action": "remove_outliers",
                "reason": f"Remove outliers using IQR. {details}"
            })

        elif itype == "high_cardinality":
            # Extract cardinality percentage if present in details
            pct_val = 0.0
            match = re.search(r"([\d.]+)%\s*of\s*rows", details)
            if match:
                try:
                    pct_val = float(match.group(1))
                except ValueError:
                    pass

            action = "drop_column" if pct_val > 80.0 else "target_encoding"
            steps.append({
                "issue": itype,
                "column": col,
                "action": action,
                "reason": f"{details}. Suggest {action}."
            })

        elif itype == "type_mismatch":
            steps.append({
                "issue": itype,
                "column": col,
                "action": "cast_datatype",
                "reason": details
            })

    return {
        "steps": steps
    }
