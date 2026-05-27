"""Data Cleaner Agent - Detects and fixes data quality issues"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DataCleanerAgent:
    """
    Agent that identifies and corrects common data quality issues.

    Capabilities
    ------------
    - Detect: missing values, duplicate rows, whitespace in strings,
               mixed-type columns, constant columns, object columns
               that look like numbers or dates.
    - Clean : drop duplicates, fill / drop missing values, strip
              whitespace, convert numeric-looking columns, parse dates,
              drop constant / all-null columns, standardise column names.
    - Audit  : every operation is recorded in a change log returned to
               the caller so the user knows exactly what was modified.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_cleaning_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Scan the dataframe and return a structured report of all issues found.

        Returns
        -------
        {
          "issues":        list[dict]   # one entry per detected issue
          "issue_count":   int
          "severity":      "clean" | "minor" | "major"
          "suggestions":   list[str]   # human-readable recommendations
        }
        """
        issues: List[Dict[str, Any]] = []

        total_cells = len(df) * len(df.columns)

        # ── Missing values ────────────────────────────────────────────
        missing = df.isnull().sum()
        cols_with_missing = missing[missing > 0]
        for col, count in cols_with_missing.items():
            pct = round(count / len(df) * 100, 1)
            issues.append({
                "type":        "missing_values",
                "column":      col,
                "count":       int(count),
                "percentage":  pct,
                "severity":    "high" if pct > 30 else "medium" if pct > 10 else "low",
                "description": f"'{col}' has {count:,} missing values ({pct}%)",
            })

        # ── Duplicate rows ────────────────────────────────────────────
        dup_count = int(df.duplicated().sum())
        if dup_count > 0:
            issues.append({
                "type":        "duplicate_rows",
                "column":      None,
                "count":       dup_count,
                "percentage":  round(dup_count / len(df) * 100, 1),
                "severity":    "high" if dup_count > len(df) * 0.05 else "medium",
                "description": f"{dup_count:,} duplicate rows detected",
            })

        # ── Whitespace in string columns ──────────────────────────────
        for col in df.select_dtypes(include="object").columns:
            try:
                has_leading  = df[col].dropna().str.startswith(" ").any()
                has_trailing = df[col].dropna().str.endswith(" ").any()
                if has_leading or has_trailing:
                    issues.append({
                        "type":        "whitespace",
                        "column":      col,
                        "count":       None,
                        "percentage":  None,
                        "severity":    "low",
                        "description": f"'{col}' contains leading/trailing whitespace",
                    })
            except Exception:
                pass

        # ── Object columns that look numeric ──────────────────────────
        for col in df.select_dtypes(include="object").columns:
            try:
                converted = pd.to_numeric(df[col].dropna(), errors="coerce")
                non_null  = df[col].dropna()
                if len(non_null) > 0 and converted.notna().sum() / len(non_null) > 0.85:
                    issues.append({
                        "type":        "wrong_dtype_numeric",
                        "column":      col,
                        "count":       None,
                        "percentage":  None,
                        "severity":    "medium",
                        "description": f"'{col}' is stored as text but looks numeric",
                    })
            except Exception:
                pass

        # ── Object columns that look like dates ───────────────────────
        for col in df.select_dtypes(include="object").columns:
            try:
                sample = df[col].dropna().head(50)
                parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
                if parsed.notna().sum() / max(len(sample), 1) > 0.8:
                    issues.append({
                        "type":        "wrong_dtype_datetime",
                        "column":      col,
                        "count":       None,
                        "percentage":  None,
                        "severity":    "low",
                        "description": f"'{col}' looks like a date column but is stored as text",
                    })
            except Exception:
                pass

        # ── Constant columns (zero variance) ──────────────────────────
        for col in df.columns:
            try:
                if df[col].nunique(dropna=True) <= 1:
                    issues.append({
                        "type":        "constant_column",
                        "column":      col,
                        "count":       None,
                        "percentage":  None,
                        "severity":    "low",
                        "description": f"'{col}' has only one unique value — likely uninformative",
                    })
            except Exception:
                pass

        # ── All-null columns ──────────────────────────────────────────
        all_null = df.columns[df.isnull().all()].tolist()
        for col in all_null:
            issues.append({
                "type":        "all_null_column",
                "column":      col,
                "count":       len(df),
                "percentage":  100.0,
                "severity":    "high",
                "description": f"'{col}' is entirely empty",
            })

        # ── Column names with spaces / special chars ───────────────────
        messy_names = [c for c in df.columns if " " in str(c) or not str(c).replace("_", "").isalnum()]
        if messy_names:
            issues.append({
                "type":        "messy_column_names",
                "column":      None,
                "count":       len(messy_names),
                "percentage":  None,
                "severity":    "low",
                "description": f"{len(messy_names)} column name(s) contain spaces or special characters",
                "columns":     messy_names,
            })

        # ── Overall severity ──────────────────────────────────────────
        severities = [i["severity"] for i in issues]
        if "high" in severities:
            overall = "major"
        elif "medium" in severities:
            overall = "minor"
        elif issues:
            overall = "minor"
        else:
            overall = "clean"

        suggestions = self._build_suggestions(issues)

        return {
            "issues":      issues,
            "issue_count": len(issues),
            "severity":    overall,
            "suggestions": suggestions,
        }

    def clean(
        self,
        df: pd.DataFrame,
        options: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Apply the selected cleaning operations and return:
          (cleaned_df, change_log)

        options keys (all bool unless noted)
        -------------------------------------
        drop_duplicates         Remove exact duplicate rows.
        fill_missing_numeric    Fill numeric NaNs with column median.
        fill_missing_categorical Fill categorical NaNs with 'Unknown'.
        drop_high_missing       Drop columns where missing > threshold (float 0-1, default 0.5).
        strip_whitespace        Strip leading/trailing whitespace from string columns.
        convert_numeric         Convert object columns that look numeric to float.
        parse_dates             Parse object columns that look like dates to datetime.
        drop_constant_cols      Drop columns with only one unique value.
        drop_all_null_cols      Drop columns that are entirely NaN.
        standardise_col_names   Lowercase + underscore column names.
        """
        cleaned  = df.copy()
        log: List[str] = []

        before_rows = len(cleaned)
        before_cols = len(cleaned.columns)

        # 1. Drop all-null columns first (before other ops reference them)
        if options.get("drop_all_null_cols", False):
            null_cols = cleaned.columns[cleaned.isnull().all()].tolist()
            if null_cols:
                cleaned.drop(columns=null_cols, inplace=True)
                log.append(f"✔ Dropped {len(null_cols)} all-null column(s): {null_cols}")

        # 2. Drop columns with too many missing values
        threshold = float(options.get("drop_high_missing_threshold", 0.5))
        if options.get("drop_high_missing", False):
            ratios     = cleaned.isnull().mean()
            to_drop    = ratios[ratios > threshold].index.tolist()
            if to_drop:
                cleaned.drop(columns=to_drop, inplace=True)
                log.append(
                    f"✔ Dropped {len(to_drop)} high-missing column(s) "
                    f"(>{int(threshold*100)}% missing): {to_drop}"
                )

        # 3. Drop constant columns
        if options.get("drop_constant_cols", False):
            const_cols = [c for c in cleaned.columns if cleaned[c].nunique(dropna=True) <= 1]
            if const_cols:
                cleaned.drop(columns=const_cols, inplace=True)
                log.append(f"✔ Dropped {len(const_cols)} constant column(s): {const_cols}")

        # 4. Drop duplicate rows
        if options.get("drop_duplicates", False):
            before = len(cleaned)
            cleaned.drop_duplicates(inplace=True)
            cleaned.reset_index(drop=True, inplace=True)
            removed = before - len(cleaned)
            if removed > 0:
                log.append(f"✔ Removed {removed:,} duplicate row(s)")

        # 5. Strip whitespace from string columns
        if options.get("strip_whitespace", False):
            str_cols = cleaned.select_dtypes(include="object").columns.tolist()
            for col in str_cols:
                try:
                    cleaned[col] = cleaned[col].str.strip()
                except Exception:
                    pass
            if str_cols:
                log.append(f"✔ Stripped whitespace from {len(str_cols)} string column(s)")

        # 6. Convert numeric-looking object columns
        if options.get("convert_numeric", False):
            converted = []
            for col in cleaned.select_dtypes(include="object").columns:
                try:
                    series = pd.to_numeric(cleaned[col], errors="coerce")
                    ratio  = series.notna().sum() / max(cleaned[col].notna().sum(), 1)
                    if ratio > 0.85:
                        cleaned[col] = series
                        converted.append(col)
                except Exception:
                    pass
            if converted:
                log.append(f"✔ Converted {len(converted)} column(s) to numeric: {converted}")

        # 7. Parse date-like object columns
        if options.get("parse_dates", False):
            parsed_cols = []
            for col in cleaned.select_dtypes(include="object").columns:
                try:
                    sample  = cleaned[col].dropna().head(50)
                    parsed  = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
                    if parsed.notna().sum() / max(len(sample), 1) > 0.8:
                        cleaned[col] = pd.to_datetime(cleaned[col], errors="coerce",
                                                       infer_datetime_format=True)
                        parsed_cols.append(col)
                except Exception:
                    pass
            if parsed_cols:
                log.append(f"✔ Parsed {len(parsed_cols)} column(s) to datetime: {parsed_cols}")

        # 8. Fill missing numeric values with column median
        if options.get("fill_missing_numeric", False):
            num_cols = cleaned.select_dtypes(include="number").columns.tolist()
            filled   = 0
            for col in num_cols:
                null_count = cleaned[col].isnull().sum()
                if null_count > 0:
                    cleaned[col].fillna(cleaned[col].median(), inplace=True)
                    filled += null_count
            if filled > 0:
                log.append(f"✔ Filled {filled:,} numeric missing value(s) with column median")

        # 9. Fill missing categorical values with 'Unknown'
        if options.get("fill_missing_categorical", False):
            cat_cols = cleaned.select_dtypes(include="object").columns.tolist()
            filled   = 0
            for col in cat_cols:
                null_count = cleaned[col].isnull().sum()
                if null_count > 0:
                    cleaned[col].fillna("Unknown", inplace=True)
                    filled += null_count
            if filled > 0:
                log.append(f"✔ Filled {filled:,} categorical missing value(s) with 'Unknown'")

        # 10. Standardise column names
        if options.get("standardise_col_names", False):
            old_names = cleaned.columns.tolist()
            new_names = (
                cleaned.columns
                .str.strip()
                .str.lower()
                .str.replace(r"[^a-z0-9]+", "_", regex=True)
                .str.strip("_")
            )
            rename_map = {o: n for o, n in zip(old_names, new_names) if o != n}
            if rename_map:
                cleaned.rename(columns=rename_map, inplace=True)
                log.append(
                    f"✔ Standardised {len(rename_map)} column name(s) "
                    f"(lowercase + underscores)"
                )

        # Summary line
        after_rows = len(cleaned)
        after_cols = len(cleaned.columns)
        row_diff   = before_rows - after_rows
        col_diff   = before_cols - after_cols

        summary_parts = []
        if row_diff:
            summary_parts.append(f"{row_diff:,} rows removed")
        if col_diff:
            summary_parts.append(f"{col_diff} columns removed")
        if not log:
            log.append("ℹ️ No operations selected — dataset unchanged.")
        else:
            summary = "  |  ".join(summary_parts) if summary_parts else "no rows/cols removed"
            log.insert(0, f"🧹 Cleaning complete — {summary}")

        return cleaned, log

    def suggest_cleaning_steps(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Return a dict of recommended default options for the clean() method
        based on the dataset's actual issues.
        """
        report  = self.get_cleaning_report(df)
        types   = {i["type"] for i in report["issues"]}

        return {
            "drop_duplicates":           "duplicate_rows"           in types,
            "fill_missing_numeric":      "missing_values"           in types,
            "fill_missing_categorical":  "missing_values"           in types,
            "drop_high_missing":         any(
                                             i["type"] == "missing_values" and i["percentage"] > 50
                                             for i in report["issues"]
                                         ),
            "drop_high_missing_threshold": 0.5,
            "strip_whitespace":          "whitespace"               in types,
            "convert_numeric":           "wrong_dtype_numeric"      in types,
            "parse_dates":               "wrong_dtype_datetime"     in types,
            "drop_constant_cols":        "constant_column"          in types,
            "drop_all_null_cols":        "all_null_column"          in types,
            "standardise_col_names":     "messy_column_names"       in types,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_suggestions(issues: List[Dict[str, Any]]) -> List[str]:
        suggestions = []
        for issue in issues:
            t = issue["type"]
            if t == "missing_values":
                pct = issue["percentage"]
                if pct > 50:
                    suggestions.append(
                        f"Drop column '{issue['column']}' — {pct}% missing is too high to impute reliably."
                    )
                else:
                    suggestions.append(
                        f"Fill missing values in '{issue['column']}' with median (numeric) or 'Unknown' (text)."
                    )
            elif t == "duplicate_rows":
                suggestions.append(
                    f"Remove {issue['count']:,} duplicate rows to avoid skewed aggregations."
                )
            elif t == "whitespace":
                suggestions.append(
                    f"Strip whitespace from '{issue['column']}' to prevent groupby mismatches."
                )
            elif t == "wrong_dtype_numeric":
                suggestions.append(
                    f"Convert '{issue['column']}' from text to numeric for calculations."
                )
            elif t == "wrong_dtype_datetime":
                suggestions.append(
                    f"Parse '{issue['column']}' as datetime to enable time-series analysis."
                )
            elif t == "constant_column":
                suggestions.append(
                    f"Consider dropping '{issue['column']}' — it carries no information."
                )
            elif t == "all_null_column":
                suggestions.append(
                    f"Drop '{issue['column']}' — it is entirely empty."
                )
            elif t == "messy_column_names":
                suggestions.append(
                    "Standardise column names to lowercase with underscores for easier querying."
                )
        return suggestions
