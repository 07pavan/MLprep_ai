from __future__ import annotations
import logging
from typing import Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def apply_cleaning_plan(
    df: pd.DataFrame,
    plan: dict[str, Any],
    action_ids: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply a deterministic cleaning plan to a pandas DataFrame.

    Supports both Phase 1 (steps) and Phase 2A (actions) plan structures.
    Supports selective execution using action_ids.

    Args:
        df: The pandas DataFrame to clean.
        plan: The dictionary containing the plan steps:
              Can be Phase 1 style:
              {
                  "steps": [
                      {"issue": str, "column": str | None, "action": str, "reason": str}
                  ]
              }
              Or Phase 2A style:
              {
                  "actions": [
                      {"action_id": str, "column_name": str | None, "recommendation": str, ...}
                  ]
              }
        action_ids: Optional list of action/step IDs to execute. If None, execute all steps.

    Returns:
        A tuple of (cleaned_df, stats) where stats is an execution audit log:
        {
            "duplicates_removed": int,
            "missing_values_filled": int,
            "outliers_removed": int,
            "outliers_clipped": int,
            "columns_dropped": list[str],
            "types_converted": list[str],
            "columns_log_transformed": int,
            "columns_frequency_encoded": int,
            "emails_cleaned": int,
            "text_trimmed": int,
            "actions_executed": list[dict]
        }
    """
    df = df.copy()
    steps = plan.get("steps") or plan.get("actions") or []

    duplicates_removed = 0
    missing_values_filled = 0
    outliers_removed = 0
    outliers_clipped = 0
    columns_dropped = []
    types_converted = []
    columns_log_transformed = 0
    columns_frequency_encoded = 0
    emails_cleaned = 0
    text_trimmed = 0
    actions_executed = []

    for step in steps:
        action_id = step.get("action_id") or step.get("id")
        action = step.get("recommendation") or step.get("action")
        col = step.get("column_name") or step.get("column")
        reason = step.get("reason", "")

        # If action_ids is specified, only execute approved actions
        if action_ids is not None:
            if action_id not in action_ids:
                logger.info("Skipping action %s (%s) as it is not in the approved list", action_id, action)
                continue

        action_norm = str(action).lower().strip()
        executed = False
        details = ""

        # ── 1. Imputation ─────────────────────────────────────────────────────
        if action_norm in ("fill_mean", "mean_imputation"):
            if col in df.columns:
                before_nulls = int(df[col].isnull().sum())
                if before_nulls > 0:
                    mean_val = df[col].mean()
                    if pd.notna(mean_val):
                        df[col] = df[col].fillna(mean_val)
                    after_nulls = int(df[col].isnull().sum())
                    filled = before_nulls - after_nulls
                    missing_values_filled += filled
                    executed = True
                    details = f"Filled {filled} missing values with mean ({mean_val})"
                else:
                    executed = True
                    details = "No missing values to fill"

        elif action_norm in ("fill_median", "median_imputation"):
            if col in df.columns:
                before_nulls = int(df[col].isnull().sum())
                if before_nulls > 0:
                    median_val = df[col].median()
                    if pd.notna(median_val):
                        df[col] = df[col].fillna(median_val)
                    after_nulls = int(df[col].isnull().sum())
                    filled = before_nulls - after_nulls
                    missing_values_filled += filled
                    executed = True
                    details = f"Filled {filled} missing values with median ({median_val})"
                else:
                    executed = True
                    details = "No missing values to fill"

        elif action_norm in ("fill_mode", "mode_imputation"):
            if col in df.columns:
                before_nulls = int(df[col].isnull().sum())
                if before_nulls > 0:
                    mode_series = df[col].mode()
                    if not mode_series.empty:
                        mode_val = mode_series.iloc[0]
                        df[col] = df[col].fillna(mode_val)
                    after_nulls = int(df[col].isnull().sum())
                    filled = before_nulls - after_nulls
                    missing_values_filled += filled
                    executed = True
                    details = f"Filled {filled} missing values with mode ({mode_val})"
                else:
                    executed = True
                    details = "No missing values to fill"

        elif action_norm in ("fill_constant", "constant_imputation"):
            if col in df.columns:
                before_nulls = int(df[col].isnull().sum())
                if before_nulls > 0:
                    const_val = step.get("constant_value")
                    if const_val is None:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            const_val = 0
                        elif pd.api.types.is_bool_dtype(df[col]):
                            const_val = False
                        else:
                            const_val = "missing"
                    df[col] = df[col].fillna(const_val)
                    after_nulls = int(df[col].isnull().sum())
                    filled = before_nulls - after_nulls
                    missing_values_filled += filled
                    executed = True
                    details = f"Filled {filled} missing values with constant value '{const_val}'"
                else:
                    executed = True
                    details = "No missing values to fill"

        # ── 2. Duplicates ─────────────────────────────────────────────────────
        elif action_norm == "remove_duplicates":
            before = len(df)
            df = df.drop_duplicates()
            after = len(df)
            removed = before - after
            duplicates_removed += removed
            executed = True
            details = f"Removed {removed} duplicate rows"

        # ── 3. Outliers ───────────────────────────────────────────────────────
        elif action_norm == "clip_outliers":
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                series = df[col].dropna()
                if len(series) >= 4:
                    q1 = series.quantile(0.25)
                    q3 = series.quantile(0.75)
                    iqr = q3 - q1
                    if iqr > 0:
                        lower = q1 - 1.5 * iqr
                        upper = q3 + 1.5 * iqr
                        before_outliers = int(((df[col] < lower) | (df[col] > upper)).sum())
                        df[col] = df[col].clip(lower=lower, upper=upper)
                        after_outliers = int(((df[col] < lower) | (df[col] > upper)).sum())
                        clipped = before_outliers - after_outliers
                        outliers_clipped += clipped
                        executed = True
                        details = f"Clipped {clipped} outliers to IQR fences [{round(lower, 2)}, {round(upper, 2)}]"
                    else:
                        executed = True
                        details = "IQR is 0, skipping clipping"
                else:
                    executed = True
                    details = "Too few values to compute IQR"

        elif action_norm == "remove_outliers":
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                series = df[col].dropna()
                if len(series) >= 4:
                    q1 = series.quantile(0.25)
                    q3 = series.quantile(0.75)
                    iqr = q3 - q1
                    if iqr > 0:
                        lower = q1 - 1.5 * iqr
                        upper = q3 + 1.5 * iqr
                        before_rows = len(df)
                        df = df[df[col].isnull() | ((df[col] >= lower) & (df[col] <= upper))]
                        after_rows = len(df)
                        removed = before_rows - after_rows
                        outliers_removed += removed
                        executed = True
                        details = f"Removed {removed} rows containing outliers"
                    else:
                        executed = True
                        details = "IQR is 0, skipping row removal"
                else:
                    executed = True
                    details = "Too few values to compute IQR"

        # ── 4. Log Transform ──────────────────────────────────────────────────
        elif action_norm == "log_transform":
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                if (df[col].dropna() >= -1).all():
                    df[col] = np.log1p(df[col])
                    columns_log_transformed += 1
                    executed = True
                    details = "Applied np.log1p log transformation"
                else:
                    executed = True
                    details = "Skipped log transform: column contains values less than -1"

        # ── 5. Frequency Encoding ─────────────────────────────────────────────
        elif action_norm == "frequency_encoding":
            if col in df.columns:
                freqs = df[col].value_counts(normalize=True).to_dict()
                df[col] = df[col].map(freqs)
                columns_frequency_encoded += 1
                executed = True
                details = "Encoded column categories with relative frequencies"

        # ── 6. Datatype Casting ───────────────────────────────────────────────
        elif action_norm == "cast_numeric":
            if col in df.columns:
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    parsed = pd.to_numeric(non_null, errors="coerce")
                    success_rate = parsed.notna().sum() / len(non_null)
                    if success_rate >= 0.80:
                        before_dtype = str(df[col].dtype)
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                        types_converted.append(f"Converted column '{col}' ({before_dtype}) to numeric")
                        executed = True
                        details = f"Cast column from {before_dtype} to numeric (success rate: {round(success_rate*100, 1)}%)"
                    else:
                        executed = True
                        details = f"Skipped casting: parse success rate {round(success_rate*100, 1)}% is below 80% threshold"
                else:
                    executed = True
                    details = "Column is empty, skipping cast"

        elif action_norm == "cast_datetime":
            if col in df.columns:
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    try:
                        parsed = pd.to_datetime(non_null, errors="coerce")
                        success_rate = parsed.notna().sum() / len(non_null)
                        if success_rate >= 0.80:
                            before_dtype = str(df[col].dtype)
                            df[col] = pd.to_datetime(df[col], errors="coerce")
                            types_converted.append(f"Converted column '{col}' ({before_dtype}) to datetime")
                            executed = True
                            details = f"Cast column from {before_dtype} to datetime (success rate: {round(success_rate*100, 1)}%)"
                        else:
                            executed = True
                            details = f"Skipped casting: parse success rate {round(success_rate*100, 1)}% is below 80% threshold"
                    except Exception as exc:
                        executed = True
                        details = f"Skipped casting: parsing encountered exception: {exc}"
                else:
                    executed = True
                    details = "Column is empty, skipping cast"

        # Backward compatibility for generic cast_datatype
        elif action_norm == "cast_datatype":
            if col in df.columns:
                reason_lower = str(reason).lower()
                before_dtype = str(df[col].dtype)
                if "numeric" in reason_lower:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    types_converted.append(f"Converted column '{col}' ({before_dtype}) to numeric")
                    executed = True
                    details = "Cast column to numeric unconditionally (legacy)"
                elif "datetime" in reason_lower:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                    types_converted.append(f"Converted column '{col}' ({before_dtype}) to datetime")
                    executed = True
                    details = "Cast column to datetime unconditionally (legacy)"
                else:
                    try:
                        df[col] = pd.to_numeric(df[col], errors="raise")
                        types_converted.append(f"Converted column '{col}' ({before_dtype}) to numeric")
                        executed = True
                        details = "Cast column to numeric successfully"
                    except Exception:
                        try:
                            df[col] = pd.to_datetime(df[col], errors="raise")
                            types_converted.append(f"Converted column '{col}' ({before_dtype}) to datetime")
                            executed = True
                            details = "Cast column to datetime successfully"
                        except Exception:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                            types_converted.append(f"Converted column '{col}' ({before_dtype}) to numeric (coerced)")
                            executed = True
                            details = "Cast column to numeric (coerced)"

        # ── 7. Email Validation ───────────────────────────────────────────────
        elif action_norm == "validate_emails":
            if col in df.columns:
                non_null_mask = df[col].notna()
                if non_null_mask.any():
                    # Strip, lowercase, and validate format
                    cleaned_series = df[col].astype(str).str.strip().str.lower()
                    invalid_mask = ~cleaned_series.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
                    before_invalid = int((non_null_mask & invalid_mask).sum())
                    df.loc[non_null_mask & invalid_mask, col] = np.nan
                    df.loc[non_null_mask & ~invalid_mask, col] = cleaned_series[~invalid_mask]
                    emails_cleaned += before_invalid
                    executed = True
                    details = f"Normalized emails. Set {before_invalid} malformed values to NaN"
                else:
                    executed = True
                    details = "No email values to validate"

        # ── 8. Trim Text ──────────────────────────────────────────────────────
        elif action_norm == "trim_text":
            if col in df.columns:
                if df[col].dtype == "object":
                    non_null_mask = df[col].notna()
                    if non_null_mask.any():
                        before_val = df.loc[non_null_mask, col].astype(str)
                        after_val = before_val.str.strip()
                        df.loc[non_null_mask, col] = after_val
                        trimmed = int((before_val != after_val).sum())
                        text_trimmed += trimmed
                        executed = True
                        details = f"Trimmed whitespace from {trimmed} text cells"
                    else:
                        executed = True
                        details = "No text cells to trim"
                else:
                    executed = True
                    details = "Skipped trimming: column is not text/object type"

        # ── 9. Drop Constant / Drop Column ────────────────────────────────────
        elif action_norm in ("drop_constant", "drop_column"):
            if col in df.columns:
                if action_norm == "drop_constant":
                    non_null = df[col].dropna()
                    if non_null.nunique() <= 1:
                        df = df.drop(columns=[col])
                        columns_dropped.append(col)
                        executed = True
                        details = "Dropped constant column"
                    else:
                        executed = True
                        details = "Skipped dropping: column is not constant"
                else:
                    df = df.drop(columns=[col])
                    columns_dropped.append(col)
                    executed = True
                    details = "Dropped column from dataset"

        # ── 10. No Action ─────────────────────────────────────────────────────
        elif action_norm == "no_action":
            executed = True
            details = "No action applied"

        if executed:
            actions_executed.append({
                "action_id": action_id,
                "column": col,
                "action": action,
                "status": "success",
                "details": details
            })

    stats = {
        "duplicates_removed": duplicates_removed,
        "missing_values_filled": missing_values_filled,
        "outliers_removed": outliers_removed,
        "outliers_clipped": outliers_clipped,
        "columns_dropped": columns_dropped,
        "types_converted": types_converted,
        "columns_log_transformed": columns_log_transformed,
        "columns_frequency_encoded": columns_frequency_encoded,
        "emails_cleaned": emails_cleaned,
        "text_trimmed": text_trimmed,
        "actions_executed": actions_executed
    }

    return df, stats
