from __future__ import annotations
import os
import uuid
import json
import logging
from typing import Any, Dict, List, Tuple, Optional

import pandas as pd
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from tools.ml_readiness_tool import score_ml_readiness
from services.dataset_service import get_dataset_service
from services.explanation_service import sanitize_pii_columns
from utils.session_manager import session_manager
from utils.llm_factory import get_llm

logger = logging.getLogger(__name__)

class InsightService:
    """Service to automatically analyze dataset metadata and generate proactive AI insights."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def generate_insights(
        self,
        user_id: str,
        session_id: str,
        category: str = "all",
        min_severity: str = "LOW"
    ) -> Dict[str, Any]:
        """Proactively analyze the dataset, caching the results based on mtime validation."""
        # 1. Cache lookup
        parquet_path = session_manager.get_data_path(user_id, session_id)
        mtime = os.path.getmtime(parquet_path) if os.path.exists(parquet_path) else 0
        cache_key = f"{user_id}_{session_id}_{category}_{min_severity}"

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.get("mtime") == mtime:
                logger.info("Insights cache hit for key %s", cache_key)
                return cached["data"]

        # 2. Load dataframe copy (Read-only isolation)
        df = session_manager.load_dataframe(user_id, session_id)
        df_copy = df.copy()

        # 3. Extract metadata & statistics (No raw rows)
        raw_metrics = {}
        original_cols = list(df_copy.columns)
        sanitized_cols, pii_mapping = sanitize_pii_columns(original_cols)

        # Run Profiler Tool
        raw_profile = profile_dataset(df_copy)
        raw_profile["column_names"] = sanitized_cols
        raw_profile["dtypes"] = {pii_mapping.get(k, k): v for k, v in raw_profile["dtypes"].items()}
        raw_metrics["profiling"] = raw_profile

        # Run Quality Tool
        raw_quality = check_quality(df_copy)
        sanitized_issues = []
        for issue in raw_quality.get("issues", []):
            iss_copy = issue.copy()
            if "column" in iss_copy and iss_copy["column"] in pii_mapping:
                iss_copy["column"] = pii_mapping[iss_copy["column"]]
            sanitized_issues.append(iss_copy)
        raw_quality["issues"] = sanitized_issues
        raw_metrics["quality"] = raw_quality

        # Run ML Readiness Tool
        raw_readiness = score_ml_readiness(df_copy)
        raw_metrics["ml_readiness"] = raw_readiness

        # Query version lineage
        lineage = []
        try:
            registry = get_dataset_service()
            datasets = registry.list_datasets(user_id)
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
            logger.warning("Failed to trace lineage for insights: %s", e)
        raw_metrics["cleaning_history"] = lineage

        # 4. Invoke LLM Insight Generator
        llm = get_llm("fast")
        success = False
        summary = ""
        insights = []

        if llm:
            try:
                prompt = self._build_prompt(raw_metrics, category, min_severity)
                response = llm.invoke(prompt)
                summary, insights = self._parse_llm_response(response.content)
                if insights:
                    success = True
            except Exception as exc:
                logger.error("LLM insight generation failed: %s", exc, exc_info=True)

        # 5. Deterministic fallback if LLM failed or parsed empty
        if not success:
            logger.info("Running deterministic insights fallback")
            summary, insights = self._generate_fallback(raw_metrics, sanitized_cols, category, min_severity)
            success = True

        # 6. Apply severity and category filtering post-generation
        filtered_insights = self._filter_insights(insights, category, min_severity)

        # Collect sources involved
        sources = ["profiler", "quality", "ml_readiness"]
        if lineage:
            sources.append("dataset_service")

        # Average confidence from insights, or default
        conf = 0.85
        if filtered_insights:
            conf = sum(item.get("confidence_score", 0.85) for item in filtered_insights) / len(filtered_insights)

        result_data = {
            "success": True,
            "insights": filtered_insights,
            "confidence": conf,
            "sources": sources,
            "metadata": {
                "summary": summary,
                "total_insights_count": len(filtered_insights),
                "session_id": session_id
            },
            "error": None
        }

        # 7. Save to cache
        self._cache[cache_key] = {
            "mtime": mtime,
            "data": result_data
        }

        return result_data

    def _build_prompt(self, metrics: Dict[str, Any], category: str, min_severity: str) -> str:
        """Construct grounded prompt feeding only aggregated metadata (never raw rows)."""
        prompt_lines = [
            "You are a Proactive AI Data Analyst. Your task is to analyze the provided dataset metadata and automatically generate key insights.",
            "You must strictly ground all findings in the provided statistics. Do not invent metrics or values.",
            "Rules:",
            "1. Output an overall summary of the dataset first.",
            "2. Generate a list of key insights. Each insight must include: insight_id (UUID), category (statistical | quality | ml_readiness | business), title, description, severity (HIGH | MEDIUM | LOW), confidence_score (float 0.0 to 1.0), source_metrics (list of tools), and recommended_actions (list of actions).",
            "3. Format your response by writing the summary first, followed by the tag '[INSIGHTS_JSON_START]', and then a single valid JSON array containing the insight objects.",
            "Example:",
            "This dataset represents transactional customer profiles...",
            "[INSIGHTS_JSON_START]",
            "[",
            "  {",
            '    "insight_id": "8bfa51de-441b-4171-beeb-9d8f8fb4a1a2",',
            '    "category": "statistical",',
            '    "title": "High Right Skew in Purchase Amount",',
            '    "description": "The purchase amount feature shows standard deviation values of...",',
            '    "severity": "MEDIUM",',
            '    "confidence_score": 0.88,',
            '    "source_metrics": ["profiler"],',
            '    "recommended_actions": ["Consider applying log transformation before model ingestion."]',
            "  }",
            "]",
            "\nMetadata inputs:"
        ]

        prof = metrics.get("profiling", {})
        prompt_lines.append(f"Row count: {prof.get('rows')}")
        prompt_lines.append(f"Column count: {prof.get('columns')}")
        prompt_lines.append(f"Column Names: {prof.get('column_names')}")
        prompt_lines.append(f"Column Types: {prof.get('dtypes')}")
        prompt_lines.append(f"Numerical stats: {prof.get('numerical_stats')}")

        q = metrics.get("quality", {})
        prompt_lines.append(f"Data quality issues detected: {q.get('issues')}")
        prompt_lines.append(f"Duplicates: {prof.get('duplicate_rows')}")

        ml = metrics.get("ml_readiness", {})
        prompt_lines.append(f"ML Readiness Score: {ml.get('score')}")
        prompt_lines.append(f"Readiness Grade: {ml.get('grade')}")
        prompt_lines.append(f"ML Strengths: {ml.get('strengths')}")
        prompt_lines.append(f"ML Weaknesses: {ml.get('weaknesses')}")

        hist = metrics.get("cleaning_history", [])
        prompt_lines.append(f"Cleaning / Version History Lineage: {hist}")

        prompt_lines.append(f"\nUser Filter constraints: Requested Category: {category}, Minimum Severity: {min_severity}")

        return "\n".join(prompt_lines)

    def _parse_llm_response(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Parse LLM output containing [INSIGHTS_JSON_START] tag into summary and insight structures."""
        if "[INSIGHTS_JSON_START]" in content:
            parts = content.split("[INSIGHTS_JSON_START]")
            summary = parts[0].strip()
            json_str = parts[1].strip()
            
            # Clean up potential markdown formatting block wraps
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            try:
                insights = json.loads(json_str)
                # Verify insights is a list of dicts
                if isinstance(insights, list):
                    verified = []
                    for item in insights:
                        if isinstance(item, dict) and "title" in item and "description" in item:
                            # Ensure required keys exist
                            item.setdefault("insight_id", str(uuid.uuid4()))
                            item.setdefault("category", "statistical")
                            item.setdefault("severity", "LOW")
                            item.setdefault("confidence_score", 0.80)
                            item.setdefault("source_metrics", ["llm"])
                            item.setdefault("recommended_actions", [])
                            verified.append(item)
                    return summary, verified
            except Exception as e:
                logger.warning("Failed to parse LLM insights JSON: %s. Raw content: %s", e, json_str)
        
        return "", []

    def _generate_fallback(
        self,
        metrics: Dict[str, Any],
        columns: List[str],
        category: str,
        min_severity: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Rule-based fallback insights generator if LLM analysis fails."""
        prof = metrics.get("profiling", {})
        rows = prof.get("rows", 0)
        cols = prof.get("columns", 0)
        summary = f"Deterministic statistical insight report for session dataset. Evaluated {rows} rows across {cols} columns."
        insights = []

        # A. Statistical Fallbacks
        insights.append({
            "insight_id": str(uuid.uuid4()),
            "category": "statistical",
            "title": f"Dataset Structure Overview",
            "description": f"The dataset contains {rows} total records and {cols} feature variables, using {prof.get('memory_mb', 0)} MB of memory.",
            "severity": "LOW",
            "confidence_score": 1.0,
            "source_metrics": ["profiler"],
            "recommended_actions": ["Review columns for redundant features."]
        })

        if prof.get("duplicate_rows", {}).get("count", 0) > 0:
            dup_count = prof["duplicate_rows"]["count"]
            dup_pct = prof["duplicate_rows"]["percentage"]
            insights.append({
                "insight_id": str(uuid.uuid4()),
                "category": "statistical",
                "title": "Duplicate Records Detected",
                "description": f"Found {dup_count} duplicate rows representing {dup_pct}% of the dataset.",
                "severity": "MEDIUM",
                "confidence_score": 1.0,
                "source_metrics": ["profiler"],
                "recommended_actions": ["Execute duplicate removal cleaning step."]
            })

        # B. Quality Fallbacks
        q = metrics.get("quality", {})
        issues = q.get("issues", [])
        for issue in issues[:5]:
            severity_map = {"missing_values": "MEDIUM", "outliers": "MEDIUM"}
            sev = severity_map.get(issue.get("type"), "LOW")
            insights.append({
                "insight_id": str(uuid.uuid4()),
                "category": "quality",
                "title": f"Quality Anomaly in Column '{issue.get('column')}'",
                "description": f"Issue: {issue.get('type').replace('_', ' ').capitalize()} - {issue.get('description')}",
                "severity": sev,
                "confidence_score": 0.95,
                "source_metrics": ["quality"],
                "recommended_actions": ["Impute missing cells or filter out anomalous outliers."]
            })

        # C. ML Readiness Fallbacks
        ml = metrics.get("ml_readiness", {})
        if ml.get("score") is not None:
            insights.append({
                "insight_id": str(uuid.uuid4()),
                "category": "ml_readiness",
                "title": f"ML Suitability Score: {ml.get('score')}/100",
                "description": f"Suitability Grade is evaluated as {ml.get('grade')}.",
                "severity": "LOW" if ml.get("score") > 75 else "MEDIUM",
                "confidence_score": 0.90,
                "source_metrics": ["ml_readiness"],
                "recommended_actions": ["Impute remaining null values and encode categories to boost grade."]
            })

        # D. Lineage/Business Fallbacks
        hist = metrics.get("cleaning_history", [])
        if len(hist) > 1:
            insights.append({
                "insight_id": str(uuid.uuid4()),
                "category": "business",
                "title": "Version History Lineage Overview",
                "description": f"Dataset has completed {len(hist)} versions. Current state is version {hist[-1].get('dataset_version')}.",
                "severity": "LOW",
                "confidence_score": 1.0,
                "source_metrics": ["dataset_service"],
                "recommended_actions": ["Maintain version track for auditing cleaning modifications."]
            })

        return summary, insights

    def _filter_insights(self, insights: List[Dict[str, Any]], category: str, min_severity: str) -> List[Dict[str, Any]]:
        """Filter insights dynamically based on requested category and severity thresholds."""
        severity_values = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        target_sev_val = severity_values.get(min_severity.upper(), 1)

        filtered = []
        for item in insights:
            # 1. Filter by category
            if category != "all" and item.get("category") != category:
                continue
            
            # 2. Filter by minimum severity
            item_sev_val = severity_values.get(item.get("severity", "LOW").upper(), 1)
            if item_sev_val < target_sev_val:
                continue

            filtered.append(item)
        return filtered


# Singleton dependency resolver
_insight_service_instance = None

def get_insight_service() -> InsightService:
    """Factory resolver for Proactive AI Insights Service layer."""
    global _insight_service_instance
    if _insight_service_instance is None:
        _insight_service_instance = InsightService()
    return _insight_service_instance
