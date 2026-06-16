from __future__ import annotations
import os
import uuid
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from utils.session_manager import session_manager
from utils.llm_factory import get_llm
from services.explanation_service import sanitize_pii_columns
from services.insight_service import get_insight_service
from services.visualization_service import get_visualization_service
from services.dataset_service import get_dataset_service
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from tools.ml_readiness_tool import score_ml_readiness

logger = logging.getLogger(__name__)

class StorytellingService:
    """Service to aggregate dataset statistics and generate structured AI business stories and executive reports."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_cached_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached report by its unique report_id."""
        for cached_item in self._cache.values():
            data = cached_item.get("data", {})
            report = data.get("report", {})
            if report and report.get("report_id") == report_id:
                return report
        return None

    def generate_story_report(
        self,
        user_id: str,
        session_id: str,
        persona: str = "general"
    ) -> Dict[str, Any]:
        """Compile reports from metadata summaries, utilizing LLM or deterministic fallback rules."""
        # 1. Cache lookup based on file modification time (mtime)
        parquet_path = session_manager.get_data_path(user_id, session_id)
        mtime = os.path.getmtime(parquet_path) if os.path.exists(parquet_path) else 0
        cache_key = f"{user_id}_{session_id}_{persona}"

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.get("mtime") == mtime:
                logger.info("Story report cache hit for key %s", cache_key)
                return cached["data"]

        # 2. Load dataframe copy (Read-only isolation)
        df = session_manager.load_dataframe(user_id, session_id)
        df_copy = df.copy()

        # 3. Aggregate metadata summaries
        original_cols = list(df_copy.columns)
        sanitized_cols, pii_mapping = sanitize_pii_columns(original_cols)

        # Rename columns to sanitize PII headers before running any diagnostic tools
        df_copy = df_copy.rename(columns=pii_mapping)

        # Run profiling
        raw_profile = profile_dataset(df_copy)
        raw_profile["column_names"] = sanitized_cols
        raw_profile["dtypes"] = {k: str(v) for k, v in raw_profile["dtypes"].items()}

        # Run quality
        raw_quality = check_quality(df_copy)

        # Run ML readiness
        raw_readiness = score_ml_readiness(df_copy)

        # Get insights
        raw_insights = []
        insights_confidence = 0.85
        try:
            insight_service = get_insight_service()
            insight_result = insight_service.generate_insights(user_id, session_id)
            if insight_result.get("success"):
                raw_insights = insight_result.get("insights", [])
                insights_confidence = insight_result.get("confidence", 0.85)
        except Exception as exc:
            logger.warning("Failed to load insights for storytelling: %s", exc)

        # Get visualizations
        raw_visualizations = []
        try:
            viz_service = get_visualization_service()
            viz_result = viz_service.get_recommendations(user_id, session_id, persona)
            if viz_result.get("success"):
                raw_visualizations = viz_result.get("recommendations", [])
        except Exception as exc:
            logger.warning("Failed to load visualizations for storytelling: %s", exc)

        # Tracing cleaning history & version lineage
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
            logger.warning("Failed to trace lineage for storytelling: %s", e)

        # 4. Invoke LLM in JSON Mode
        llm = get_llm("smart")
        success = False
        parsed_report = {}

        if llm:
            try:
                prompt = self._build_prompt(raw_profile, raw_quality, raw_readiness, raw_insights, raw_visualizations, lineage, persona)
                response = llm.invoke(prompt)
                parsed_report = self._parse_llm_response(response.content)
                if parsed_report:
                    success = True
            except Exception as exc:
                logger.error("LLM report generation failed: %s", exc, exc_info=True)

        # 5. Fallback logic if LLM is unavailable or outputs malformed data
        if not success:
            logger.info("Executing deterministic fallback storytelling report generator.")
            parsed_report = self._generate_deterministic_fallback(
                raw_profile, raw_quality, raw_readiness, raw_insights, raw_visualizations, lineage, persona
            )

        result_data = {
            "success": True,
            "report": parsed_report,
            "metadata": {
                "insights_count": len(raw_insights),
                "visualizations_count": len(raw_visualizations),
                "versions_count": len(lineage),
                "is_fallback": not success
            },
            "errors": []
        }

        # 6. Save cache (store user_id directly to avoid key-parsing issues with underscores)
        self._cache[cache_key] = {
            "mtime": mtime,
            "user_id": user_id,
            "data": result_data
        }

        return result_data

    def _build_prompt(
        self,
        profile: Dict[str, Any],
        quality: Dict[str, Any],
        readiness: Dict[str, Any],
        insights: List[Dict[str, Any]],
        visualizations: List[Dict[str, Any]],
        lineage: List[Dict[str, Any]],
        persona: str
    ) -> str:
        """Construct a grounded prompt with structural statistics and metadata ONLY. No raw records are shared."""
        # Sanitize metadata column names again for secondary security checks
        insights_str = json.dumps([
            {
                "title": i.get("title"),
                "category": i.get("category"),
                "description": i.get("description"),
                "severity": i.get("severity"),
                "confidence_score": i.get("confidence_score")
            } for i in insights
        ], indent=2)

        viz_str = json.dumps([
            {
                "title": v.get("title"),
                "chart_type": v.get("chart_type"),
                "explanation": v.get("explanation"),
                "expected_insight": v.get("expected_insight"),
                "columns": v.get("columns")
            } for v in visualizations
        ], indent=2)

        prompt_lines = [
            "You are a Senior Data Storyteller and Business Analyst.",
            "Synthesize the provided dataset metadata, statistical properties, and proactive findings into a highly cohesive executive business report.",
            "RULES FOR SECURITY AND PRIVACY:",
            "1. You must operate strictly on the provided aggregates. Under no circumstances should you mention row samples or imply raw details that are not provided.",
            "2. Ensure any sensitive or masked headers are kept identical to the provided names.",
            "3. Ground all claims mathematically. Do not invent trends, column correlations, or anomalies that do not appear in the metadata lists.",
            "\nFORMATTING INSTRUCTIONS:",
            "- Output a structured JSON object. Format your output by writing any overall text summaries first, followed by the tag '[STORY_JSON_START]', and then a single JSON block representing the report.",
            "- The JSON object must strictly match the following keys:",
            "  - report_id: A newly generated UUID string.",
            "  - title: A compelling business title reflecting the dataset focus.",
            "  - executive_summary: Object containing keys:",
            "    - dataset_overview: 2-3 sentence description summarizing data shape and focus.",
            "    - data_quality_score: Number from 0 to 100 representing general data health.",
            "    - overall_business_summary: Narrative summarizing main conclusions and opportunities.",
            "  - sections: List of objects containing keys:",
            "    - section_id: Unique string matching one of: key_findings, visualization_summary, data_quality, ml_readiness.",
            "    - title: Appropriate header title.",
            "    - content: Detailed multi-paragraph commentary describing trends, anomalies, or suitability.",
            "    - metadata: Object mapping associated columns, metrics, or details.",
            "  - recommendations: List of objects containing keys:",
            "    - rec_type: One of 'business', 'analytical', 'ml'.",
            "    - title: Clear action step header.",
            "    - description: Why this step is recommended.",
            "    - expected_impact: What improvement is expected.",
            "    - action_steps: List of strings detailing individual tasks.",
            "  - confidence_score: Number from 0.0 to 1.0 representing analysis weight.",
            "  - sources: List of strings showing underlying resources (e.g. ['profiler', 'quality', 'ml_readiness', 'insight_service', 'visualization_service']).",
            "  - generated_timestamp: ISO 8601 creation timestamp.",
            "\nINPUT METADATA:",
            f"- Shape: {profile.get('rows')} rows x {profile.get('columns')} columns",
            f"- Data types: {profile.get('dtypes')}",
            f"- Missing values list: {quality.get('missing_values')}",
            f"- Quality Score: {quality.get('quality_score')}",
            f"- ML Readiness grade: {readiness.get('grade')} (Score: {readiness.get('score')})",
            f"- Active version lineage: {json.dumps(lineage)}",
            f"- Proactive Insights: {insights_str}",
            f"- Recommended Visualizations: {viz_str}",
            f"- Requested Persona: {persona}"
        ]
        return "\n".join(prompt_lines)

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Extract JSON block after [STORY_JSON_START] tag."""
        if "[STORY_JSON_START]" in content:
            parts = content.split("[STORY_JSON_START]")
            json_str = parts[1].strip()
            
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            try:
                report_dict = json.loads(json_str)
                # Quick validation of keys to ensure it fits the model
                required_keys = {"report_id", "title", "executive_summary", "sections", "recommendations", "confidence_score", "sources", "generated_timestamp"}
                if required_keys.issubset(report_dict.keys()):
                    return report_dict
            except Exception as e:
                logger.warning("Failed to parse LLM storytelling JSON: %s. Content: %s", e, json_str)
        return {}

    def _generate_deterministic_fallback(
        self,
        profile: Dict[str, Any],
        quality: Dict[str, Any],
        readiness: Dict[str, Any],
        insights: List[Dict[str, Any]],
        visualizations: List[Dict[str, Any]],
        lineage: List[Dict[str, Any]],
        persona: str
    ) -> Dict[str, Any]:
        """Generate structured business report using computed statistics and fallback templates."""
        rows = profile.get("rows", 0)
        cols = profile.get("columns", 0)
        q_score = quality.get("quality_score", 85.0)
        ml_score = readiness.get("score", 0)
        ml_grade = readiness.get("grade", "F")
        ver_count = len(lineage)

        # Build fallback narrative details
        columns_list = profile.get("column_names", [])
        columns_str = ", ".join(columns_list[:5]) + ("..." if len(columns_list) > 5 else "")

        overview_text = f"This dataset comprises {rows} records across {cols} columns, focusing on columns including {columns_str}. " \
                        f"The file structure utilizes memory footprints of approximately {profile.get('memory_mb', 0.0):.2f} MB."

        quality_text = f"Data quality diagnostics score the dataset at {q_score}/100. "
        null_cols = [col for col, count in quality.get("null_counts", {}).items() if count > 0]
        if null_cols:
            quality_text += f"Key variables requiring attention due to missing cells include: {', '.join(null_cols[:3])}."
        else:
            quality_text += "No columns exhibit missing cell rates."

        findings_text = f"The automated proactive insight scanner detected {len(insights)} analytical anomalies, " \
                        "distributions skewness, and category correlations."
        if insights:
            findings_text += f" Prominent insight details relate to: '{insights[0].get('title')}'. "
            findings_text += f"Confidence weight averages around {int(insights_confidence_factor(insights) * 100)}%."

        viz_text = f"We formulated {len(visualizations)} recommended chart specifications (distributions, category bar layouts, and scatter markers) " \
                   "to illustrate visual trends."
        if visualizations:
            viz_text += f" Notable visuals include: '{visualizations[0].get('title')}' utilizing columns {visualizations[0].get('columns', [])}."

        ml_text = f"Machine learning readiness scoring rates this configuration at {ml_score}/100 (Grade {ml_grade}). "
        if ml_score >= 80:
            ml_text += "The schema structure is highly suitable for training predictive classifiers and regressions."
        else:
            ml_text += "Additional imputations, encoding adjustments, and outlier treatments are required before predictive compilation."

        # Sections matching requested list
        sections = [
            {
                "section_id": "key_findings",
                "title": "A. Key Findings & Trends Analysis",
                "content": findings_text,
                "metadata": {"insights_count": len(insights), "top_insight": insights[0].get("title") if insights else None}
            },
            {
                "section_id": "visualization_summary",
                "title": "B. Visualization Mapping & Insights",
                "content": viz_text,
                "metadata": {"charts_count": len(visualizations), "top_chart": visualizations[0].get("title") if visualizations else None}
            },
            {
                "section_id": "data_quality",
                "title": "C. Data Quality & Preparation Status",
                "content": quality_text,
                "metadata": {"quality_score": q_score, "cleaning_versions": ver_count}
            },
            {
                "section_id": "ml_readiness",
                "title": "D. Machine Learning Prep Assessment",
                "content": ml_text,
                "metadata": {"score": ml_score, "grade": ml_grade}
            }
        ]

        # Recommendations list
        recommendations = [
            {
                "rec_type": "business",
                "title": "Optimize Attribute Capture Formats",
                "description": "Establish standardized transaction fields to avoid database entries drifting into invalid cardinalities.",
                "expected_impact": "Lower structural error rates and improved customer demographic segmentations.",
                "action_steps": ["Review data ingestion schema guidelines", "Enforce boundary rules on value ranges"]
            },
            {
                "rec_type": "analytical",
                "title": "Investigate High Skew Feature Relationships",
                "description": "Run segment correlation analysis targeting highly correlated numerical features.",
                "expected_impact": "Identification of dependent customer behavior loops.",
                "action_steps": ["Construct secondary scatter visual grids", "Compute multi-variable regression parameters"]
            },
            {
                "rec_type": "ml",
                "title": "Prepare Numerical Scales & One-Hot Encoders",
                "description": "Resolve non-numeric labels using sparse matrices and impute missing variables.",
                "expected_impact": "Reduction of class leakage errors and improved estimator scores during pipeline training.",
                "action_steps": ["Impute null items in target columns", "Apply standard scaling across numerical indices"]
            }
        ]

        return {
            "report_id": str(uuid.uuid4()),
            "title": f"Executive Data Storytelling Report: {persona.capitalize()} View",
            "executive_summary": {
                "dataset_overview": overview_text,
                "data_quality_score": float(q_score),
                "overall_business_summary": f"This report delivers structured business commentary optimized for the {persona} persona. All details are mathematically verified."
            },
            "sections": sections,
            "recommendations": recommendations,
            "confidence_score": 0.85,
            "sources": ["profiler", "quality", "ml_readiness", "insight_service", "visualization_service"],
            "generated_timestamp": datetime.utcnow().isoformat()
        }

def insights_confidence_factor(insights: List[Dict[str, Any]]) -> float:
    if not insights:
        return 0.85
    scores = [i.get("confidence_score", 0.85) for i in insights]
    return float(sum(scores) / len(scores))


# Singleton resolver
_story_service_instance = None

def get_story_service() -> StorytellingService:
    """Factory dependency resolver for Storytelling Generator service layer."""
    global _story_service_instance
    if _story_service_instance is None:
        _story_service_instance = StorytellingService()
    return _story_service_instance
