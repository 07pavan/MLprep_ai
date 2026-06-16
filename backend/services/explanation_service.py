from __future__ import annotations
import os
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from tools.ml_readiness_tool import score_ml_readiness
from services.dataset_service import get_dataset_service
from utils.session_manager import session_manager
from utils.llm_factory import get_llm

logger = logging.getLogger(__name__)

PII_KEYWORDS = {"name", "email", "phone", "ssn", "social", "address", "password", "credit", "card", "zip", "location"}

def sanitize_pii_columns(columns: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """Scan columns for potential PII keywords and replace them with anonymous tags."""
    sanitized = []
    mapping = {}
    pii_counter = 1
    for col in columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in PII_KEYWORDS):
            anon_name = f"[ANONYMIZED_PII_{pii_counter}]"
            mapping[col] = anon_name
            sanitized.append(anon_name)
            pii_counter += 1
        else:
            sanitized.append(col)
    return sanitized, mapping


class ExplanationService:
    """Service to compile dataset summaries and generate semantic explanations."""
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_explanation(
        self,
        user_id: str,
        session_id: str,
        aspect: str,
        persona: str = "general"
    ) -> Dict[str, Any]:
        """Generate or retrieve dataset explanations for the selected aspect."""
        # 1. Cache lookup
        parquet_path = session_manager.get_data_path(user_id, session_id)
        mtime = os.path.getmtime(parquet_path) if os.path.exists(parquet_path) else 0
        cache_key = f"{user_id}_{session_id}_{aspect}"

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.get("mtime") == mtime:
                logger.info("Explanation cache hit for %s", cache_key)
                return cached["data"]

        # 2. Load dataframe copy
        df = session_manager.load_dataframe(user_id, session_id)
        df_copy = df.copy()

        # 3. Retrieve metadata depending on aspect
        raw_metrics = {}
        sources = []
        
        # PII column sanitization
        original_cols = list(df_copy.columns)
        sanitized_cols, pii_mapping = sanitize_pii_columns(original_cols)

        if aspect == "profiling" or aspect == "general":
            raw_profile = profile_dataset(df_copy)
            # Anonymize PII column names in profiling metrics
            raw_profile["column_names"] = sanitized_cols
            raw_profile["dtypes"] = {pii_mapping.get(k, k): v for k, v in raw_profile["dtypes"].items()}
            raw_metrics["profiling"] = raw_profile
            sources.append("profiler")

        if aspect == "quality" or aspect == "general":
            raw_quality = check_quality(df_copy)
            # Anonymize column names in quality issues
            sanitized_issues = []
            for issue in raw_quality.get("issues", []):
                iss_copy = issue.copy()
                if "column" in iss_copy and iss_copy["column"] in pii_mapping:
                    iss_copy["column"] = pii_mapping[iss_copy["column"]]
                sanitized_issues.append(iss_copy)
            raw_quality["issues"] = sanitized_issues
            raw_metrics["quality"] = raw_quality
            sources.append("quality")

        if aspect == "ml_readiness" or aspect == "general":
            raw_readiness = score_ml_readiness(df_copy)
            raw_metrics["ml_readiness"] = raw_readiness
            sources.append("ml_readiness")

        if aspect == "cleaning_history":
            # Trace version history in dataset registry
            lineage = []
            try:
                registry = get_dataset_service()
                datasets = registry.list_datasets(user_id)
                # Find current dataset matching this parquet path
                current_ds = None
                for ds in datasets:
                    if ds.get("parquet_path") == parquet_path:
                        current_ds = ds
                        break
                
                curr = current_ds
                while curr:
                    lineage.append({
                        "dataset_id": curr.get("dataset_id"),
                        "dataset_name": curr.get("dataset_name"),
                        "dataset_version": curr.get("dataset_version"),
                        "row_count": curr.get("row_count"),
                        "column_count": curr.get("column_count"),
                        "upload_timestamp": curr.get("upload_timestamp"),
                        "parent_dataset_id": curr.get("parent_dataset_id")
                    })
                    parent_id = curr.get("parent_dataset_id")
                    if parent_id:
                        curr = registry.get_dataset(parent_id)
                    else:
                        curr = None
                lineage.reverse()
            except Exception as e:
                logger.warning("Failed to trace lineage for explanation: %s", e)
            raw_metrics["cleaning_history"] = lineage
            sources.append("dataset_service")

        # 4. Prompt construction & LLM explanation call
        llm = get_llm("fast")  # Use fast tier LLM for explanations
        success = False
        summary = ""
        insights = []
        confidence = 0.50

        if llm:
            try:
                prompt = self._build_prompt(aspect, raw_metrics, persona)
                response = llm.invoke(prompt)
                summary, insights = self._parse_llm_response(response.content)
                success = True
                confidence = 0.90
            except Exception as exc:
                logger.error("LLM explanation invocation failed: %s", exc, exc_info=True)
                # Fall back to deterministic code path

        # 5. Deterministic fallback if LLM failed or was missing
        if not success:
            logger.info("Running deterministic explanation fallback for aspect %s", aspect)
            summary, insights = self._generate_fallback(aspect, raw_metrics, sanitized_cols)
            success = True
            confidence = 0.70

        result_data = {
            "success": True,
            "summary": summary,
            "insights": insights,
            "confidence": confidence,
            "sources": sources,
            "raw_metrics": raw_metrics,
            "error": None
        }

        # 6. Save in cache
        self._cache[cache_key] = {
            "mtime": mtime,
            "data": result_data
        }

        return result_data

    def _build_prompt(self, aspect: str, metrics: Dict[str, Any], persona: str) -> str:
        """Construct a grounded prompt sending only statistical metrics (never raw rows)."""
        prompt_lines = [
            f"You are a Senior Data Analyst describing a dataset under a '{persona}' persona context.",
            "Describe the data structures, shapes, and anomalies based strictly on the provided metadata.",
            "Rules:",
            "1. Ground your answer only in the metrics provided. Do not invent any numbers.",
            "2. Focus on plain-language explanations.",
            "3. Format your output with an 'Overview Summary' section first, followed by a 'Key Insights' list (use bullet points).",
            "4. Separate the summary and the bullet points list using the tag '[INSIGHTS_START]'.",
            "\nMetadata inputs:"
        ]

        if aspect == "profiling" and "profiling" in metrics:
            prof = metrics["profiling"]
            prompt_lines.append(f"Row count: {prof.get('rows')}")
            prompt_lines.append(f"Column count: {prof.get('columns')}")
            prompt_lines.append(f"Columns: {prof.get('column_names')}")
            prompt_lines.append(f"Column Types: {prof.get('dtypes')}")
            prompt_lines.append(f"Numerical stats: {prof.get('numerical_stats')}")

        elif aspect == "quality" and "quality" in metrics:
            q = metrics["quality"]
            prompt_lines.append(f"Data quality issues detected: {q.get('issues')}")

        elif aspect == "ml_readiness" and "ml_readiness" in metrics:
            ml = metrics["ml_readiness"]
            prompt_lines.append(f"ML Readiness Score: {ml.get('score')}")
            prompt_lines.append(f"Readiness Grade: {ml.get('grade')}")
            prompt_lines.append(f"Strengths: {ml.get('strengths')}")
            prompt_lines.append(f"Weaknesses: {ml.get('weaknesses')}")

        elif aspect == "cleaning_history" and "cleaning_history" in metrics:
            history = metrics["cleaning_history"]
            prompt_lines.append(f"Dataset Version Lineage: {history}")

        else:
            # General overview
            prompt_lines.append(f"Overview Metrics: {metrics}")

        return "\n".join(prompt_lines)

    def _parse_llm_response(self, content: str) -> Tuple[str, List[str]]:
        """Parse LLM output into a summary block and insights list."""
        if "[INSIGHTS_START]" in content:
            parts = content.split("[INSIGHTS_START]")
            summary = parts[0].replace("Overview Summary:", "").strip()
            insights_raw = parts[1].strip().split("\n")
            insights = [line.replace("*", "").replace("-", "").strip() for line in insights_raw if line.strip()]
            return summary, insights
        
        # Fallback parser if LLM omitted the tag
        lines = content.strip().split("\n")
        summary_lines = []
        insights = []
        in_list = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("-") or stripped.startswith("*") or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == '.'):
                in_list = True
                insights.append(stripped.lstrip("-*0123456789. "))
            elif not in_list:
                summary_lines.append(stripped)
            else:
                insights.append(stripped)
                
        return " ".join(summary_lines), insights

    def _generate_fallback(self, aspect: str, metrics: Dict[str, Any], columns: List[str]) -> Tuple[str, List[str]]:
        """A complete deterministic generator returning clean statistical insights if LLM call fails."""
        if aspect == "profiling" and "profiling" in metrics:
            prof = metrics["profiling"]
            summary = f"This dataset contains {prof.get('rows')} rows and {prof.get('columns')} columns. The table uses {prof.get('memory_mb')} MB of memory."
            insights = [
                f"Features include: {', '.join(columns[:8])}" + ("..." if len(columns) > 8 else ""),
                f"Contains {prof.get('numerical_count')} numeric columns and {prof.get('categorical_count')} categorical columns.",
                f"Duplicate rows account for {prof.get('duplicate_rows', {}).get('count')} rows ({prof.get('duplicate_rows', {}).get('percentage')}%)."
            ]
            return summary, insights

        elif aspect == "quality" and "quality" in metrics:
            q = metrics["quality"]
            issues = q.get("issues", [])
            summary = f"Identified {len(issues)} structural issues in the dataset."
            insights = [f"{i.get('type').replace('_', ' ').capitalize()} in column '{i.get('column')}': {i.get('description')}" for i in issues[:5]]
            if len(issues) > 5:
                insights.append(f"... and {len(issues) - 5} other data quality warnings.")
            if not issues:
                insights = ["No data quality issues or anomalies detected in features."]
            return summary, insights

        elif aspect == "ml_readiness" and "ml_readiness" in metrics:
            ml = metrics["ml_readiness"]
            summary = f"ML suitability grade is {ml.get('grade')} with a score of {ml.get('score')}/100."
            insights = []
            for s in ml.get("strengths", [])[:3]:
                insights.append(f"Strength: {s}")
            for w in ml.get("weaknesses", [])[:3]:
                insights.append(f"Weakness: {w}")
            return summary, insights

        elif aspect == "cleaning_history" and "cleaning_history" in metrics:
            history = metrics["cleaning_history"]
            summary = f"Dataset version lineage tracks {len(history)} total versions."
            insights = [f"Version {h.get('dataset_version')} ({h.get('dataset_name')}): {h.get('row_count')} rows x {h.get('column_count')} columns." for h in history]
            return summary, insights

        else:
            # General aspect fallback
            rows = metrics.get("profiling", {}).get("rows", "unknown")
            cols = metrics.get("profiling", {}).get("columns", "unknown")
            summary = f"General overview of dataset. The structure consists of {rows} records across {cols} features."
            insights = [
                "Profiling statistics successfully processed.",
                "Quality anomalies mapped to issue tables.",
                "ML readiness scores evaluated."
            ]
            return summary, insights


# Singleton instance
_explanation_service_instance = None

def get_explanation_service():
    """Factory dependency resolver for dataset explanation service layer."""
    global _explanation_service_instance
    if _explanation_service_instance is None:
        _explanation_service_instance = ExplanationService()
    return _explanation_service_instance
