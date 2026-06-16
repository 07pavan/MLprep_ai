from __future__ import annotations
import os
import uuid
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from utils.session_manager import session_manager
from utils.llm_factory import get_llm
from services.explanation_service import sanitize_pii_columns
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality

logger = logging.getLogger(__name__)

class VisualizationService:
    """Service to automatically recommend, specify, and explain dataset visualizations."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_recommendations(
        self,
        user_id: str,
        session_id: str,
        persona: str = "general"
    ) -> Dict[str, Any]:
        """Generate, explain, and cache visualization recommendations."""
        # 1. Cache lookup
        parquet_path = session_manager.get_data_path(user_id, session_id)
        mtime = os.path.getmtime(parquet_path) if os.path.exists(parquet_path) else 0
        cache_key = f"{user_id}_{session_id}_{persona}"

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.get("mtime") == mtime:
                logger.info("Visualizations cache hit for key %s", cache_key)
                return cached["data"]

        # 2. Load dataframe copy (Read-only isolation)
        df = session_manager.load_dataframe(user_id, session_id)
        df_copy = df.copy()

        # 3. Aggregated metadata & metrics (PII column masking)
        original_cols = list(df_copy.columns)
        sanitized_cols, pii_mapping = sanitize_pii_columns(original_cols)

        raw_profile = profile_dataset(df_copy)
        raw_quality = check_quality(df_copy)

        # 4. Generate deterministic candidates & Vega specs
        candidates, sampled_records = self._generate_candidates(df_copy, raw_profile, raw_quality, pii_mapping)

        # 5. LLM interpretation call for narrative descriptions
        llm = get_llm("fast")
        success = False
        enhanced_mapping = {}

        if llm:
            try:
                prompt = self._build_prompt(raw_profile, raw_quality, candidates, persona)
                response = llm.invoke(prompt)
                enhanced_mapping = self._parse_llm_response(response.content)
                if enhanced_mapping:
                    success = True
            except Exception as exc:
                logger.error("LLM visualization enhancement failed: %s", exc, exc_info=True)

        # 6. Apply explanations (LLM or deterministic fallbacks)
        recommendations = []
        for cand in candidates:
            cand_id = cand["visualization_id"]
            title = cand["title"]
            description = cand["description"]
            business_reason = cand["business_reason"]
            expected_insight = cand["expected_insight"]
            explanation = cand["explanation"]

            # Overlay LLM enhancements if available
            if success and cand_id in enhanced_mapping:
                enhanced = enhanced_mapping[cand_id]
                title = enhanced.get("title", title)
                description = enhanced.get("description", description)
                business_reason = enhanced.get("business_reason", business_reason)
                expected_insight = enhanced.get("expected_insight", expected_insight)
                explanation = enhanced.get("explanation", explanation)

            # Build final rendering config with sampled records embedded
            rendering_config = cand["rendering_config"].copy()
            # Heatmaps and quality charts manage their own embedded data, other charts reference sampled records
            if "data" not in rendering_config:
                rendering_config["data"] = {"values": sampled_records}

            recommendations.append({
                "visualization_id": cand_id,
                "chart_type": cand["chart_type"],
                "columns": cand["columns"],
                "title": title,
                "description": description,
                "business_reason": business_reason,
                "confidence_score": cand["confidence_score"],
                "source_metrics": cand["source_metrics"],
                "rendering_config": rendering_config,
                "explanation": explanation,
                "expected_insight": expected_insight
            })

        result_data = {
            "success": True,
            "recommendations": recommendations,
            "error": None
        }

        # 7. Save to cache
        self._cache[cache_key] = {
            "mtime": mtime,
            "data": result_data
        }

        return result_data

    def _generate_candidates(
        self,
        df: pd.DataFrame,
        profile: Dict[str, Any],
        quality: Dict[str, Any],
        pii_mapping: Dict[str, str]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Programmatically detect dataset properties and build visualization specs with fallbacks."""
        candidates = []
        
        # Performance: Sample up to 1,000 records locally to prevent browser rendering issues
        sampled_df = df.sample(n=min(1000, len(df)), random_state=42)
        # Convert PII columns in sampled records
        sampled_df = sampled_df.rename(columns=pii_mapping)
        sampled_records = sampled_df.to_dict(orient="records")

        # Column classification
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []

        for col in df.columns:
            sanitized_name = pii_mapping.get(col, col)
            if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
                # If unique counts is very low and dataset is large enough, treat as categorical
                if df[col].nunique() <= 5 and len(df) > 8:
                    categorical_cols.append((col, sanitized_name, df[col].nunique()))
                else:
                    numeric_cols.append((col, sanitized_name))
            elif pd.api.types.is_datetime64_any_dtype(df[col]) or "date" in col.lower() or "time" in col.lower():
                datetime_cols.append((col, sanitized_name))
            else:
                categorical_cols.append((col, sanitized_name, df[col].nunique()))

        # 1. Distribution Analysis (Histogram + Box Plot)
        for col, s_name in numeric_cols[:2]:
            # Histogram
            cand_id = str(uuid.uuid4())
            candidates.append({
                "visualization_id": cand_id,
                "chart_type": "histogram",
                "columns": [s_name],
                "title": f"Distribution of {s_name}",
                "description": f"Histogram showing the frequency distribution for column '{s_name}'.",
                "business_reason": "Identifies the data range concentration, shape profiles, and data gaps.",
                "confidence_score": 0.95,
                "source_metrics": ["profiler"],
                "explanation": f"The height of each bar represents the frequency of data points in that range. Observe where values peak.",
                "expected_insight": "Detects whether values cluster centrally or skew heavily.",
                "rendering_config": {
                    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                    "title": f"Distribution of {s_name}",
                    "width": "container",
                    "height": 280,
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": s_name, "type": "quantitative", "bin": True},
                        "y": {"aggregate": "count", "type": "quantitative"}
                    }
                }
            })

            # Box Plot (If outliers are present or standard IQR suggests)
            # Simple IQR check
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            outliers = df[(df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))]
            if len(outliers) > 0:
                candidates.append({
                    "visualization_id": str(uuid.uuid4()),
                    "chart_type": "box",
                    "columns": [s_name],
                    "title": f"Outlier Analysis: {s_name}",
                    "description": f"Box plot representing the spread, median, and extreme outlier points of '{s_name}'.",
                    "business_reason": "Enables isolation of erroneous transactions, input anomalies, or valid extremes.",
                    "confidence_score": 0.90,
                    "source_metrics": ["quality"],
                    "explanation": "The box outlines the Interquartile Range (IQR), the middle line is the median, and outer points are outliers.",
                    "expected_insight": "Identify extreme values lying beyond the standard quartile whiskers.",
                    "rendering_config": {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "title": f"Outlier Spread of {s_name}",
                        "width": "container",
                        "height": 280,
                        "mark": "boxplot",
                        "encoding": {
                            "y": {"field": s_name, "type": "quantitative"}
                        }
                    }
                })

        # 2. Category Analysis (Bar + Pie)
        for col, s_name, nunique in categorical_cols[:2]:
            if nunique <= 5:
                # Pie Chart for low-cardinality
                candidates.append({
                    "visualization_id": str(uuid.uuid4()),
                    "chart_type": "pie",
                    "columns": [s_name],
                    "title": f"Proportion of {s_name}",
                    "description": f"Pie chart showing proportion share of column '{s_name}'.",
                    "business_reason": "Best for comparing relative shares of few category levels (parts-to-whole).",
                    "confidence_score": 0.85,
                    "source_metrics": ["profiler"],
                    "explanation": "Segments reflect the relative percentage of each level. Watch for segments taking up the majority.",
                    "expected_insight": "Visualize the dominant category and relative shares.",
                    "rendering_config": {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "title": f"Proportion share of {s_name}",
                        "width": "container",
                        "height": 280,
                        "mark": {"type": "arc", "innerRadius": 40},
                        "encoding": {
                            "theta": {"aggregate": "count", "type": "quantitative"},
                            "color": {"field": s_name, "type": "nominal"}
                        }
                    }
                })
            elif 5 < nunique <= 20:
                # Bar Chart
                candidates.append({
                    "visualization_id": str(uuid.uuid4()),
                    "chart_type": "bar",
                    "columns": [s_name],
                    "title": f"Category Breakdown: {s_name}",
                    "description": f"Bar chart showing category sizes for column '{s_name}'.",
                    "business_reason": "Ideal for comparing frequency differences between different groups.",
                    "confidence_score": 0.90,
                    "source_metrics": ["profiler"],
                    "explanation": "Each vertical bar represents the record frequency of that category.",
                    "expected_insight": "Instantly compare bar sizes to see group rankings.",
                    "rendering_config": {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "title": f"Category Breakdown: {s_name}",
                        "width": "container",
                        "height": 280,
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": s_name, "type": "nominal", "sort": "-y"},
                            "y": {"aggregate": "count", "type": "quantitative"},
                            "color": {"field": s_name, "type": "nominal", "legend": None}
                        }
                    }
                })

        # 3. Time Series Analysis (Line Chart)
        if datetime_cols and numeric_cols:
            date_col, date_sname = datetime_cols[0]
            num_col, num_sname = numeric_cols[0]
            candidates.append({
                "visualization_id": str(uuid.uuid4()),
                "chart_type": "line",
                "columns": [date_sname, num_sname],
                "title": f"{num_sname} Trend over Time",
                "description": f"Line chart mapping values of '{num_sname}' across '{date_sname}' indices.",
                "business_reason": "Discovers seasonality, cycle peaks, performance growth, or decline trajectories.",
                "confidence_score": 0.95,
                "source_metrics": ["profiler"],
                "explanation": "Follow the line sequence from left to right to trace performance drift over time.",
                "expected_insight": "Identify growth cycles, sudden drops, or cyclical peak indices.",
                "rendering_config": {
                    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                    "title": f"Trend: {num_sname} over {date_sname}",
                    "width": "container",
                    "height": 280,
                    "mark": "line",
                    "encoding": {
                        "x": {"field": date_sname, "type": "temporal"},
                        "y": {"field": num_sname, "type": "quantitative"}
                    }
                }
            })

        # 4. Correlation Analysis (Scatter + Heatmap)
        if len(numeric_cols) >= 2:
            num1_col, num1_sname = numeric_cols[0]
            num2_col, num2_sname = numeric_cols[1]
            candidates.append({
                "visualization_id": str(uuid.uuid4()),
                "chart_type": "scatter",
                "columns": [num1_sname, num2_sname],
                "title": f"Correlation: {num1_sname} vs {num2_sname}",
                "description": f"Scatter plot mapping '{num1_sname}' values against '{num2_sname}'.",
                "business_reason": "Evaluates numerical dependencies, cluster groupings, or outlier relationships.",
                "confidence_score": 0.90,
                "source_metrics": ["profiler"],
                "explanation": "Each dot represents a record. Symmetrical clusters indicate strong correlation.",
                "expected_insight": "Spot linear patterns or groupings indicating dependencies.",
                "rendering_config": {
                    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                    "title": f"Correlation: {num1_sname} vs {num2_sname}",
                    "width": "container",
                    "height": 280,
                    "mark": "point",
                    "encoding": {
                        "x": {"field": num1_sname, "type": "quantitative"},
                        "y": {"field": num2_sname, "type": "quantitative"}
                    }
                }
            })

        # Heatmap correlation matrix (if 3 to 10 numeric columns)
        if 3 <= len(numeric_cols) <= 10:
            num_names = [sname for _, sname in numeric_cols]
            # Compute correlation matrix locally
            try:
                corr_df = df[[col for col, _ in numeric_cols]].corr().round(2).fillna(0.0)
                corr_records = []
                for c1 in corr_df.columns:
                    s1 = pii_mapping.get(c1, c1)
                    for c2 in corr_df.columns:
                        s2 = pii_mapping.get(c2, c2)
                        corr_records.append({
                            "var1": s1,
                            "var2": s2,
                            "correlation": float(corr_df.loc[c1, c2])
                        })

                candidates.append({
                    "visualization_id": str(uuid.uuid4()),
                    "chart_type": "heatmap",
                    "columns": num_names,
                    "title": "Numerical Feature Correlation Matrix",
                    "description": "Correlation matrix heatmap checking collinearity across all numeric variables.",
                    "business_reason": "Flags highly redundant features that should be filtered before model training.",
                    "confidence_score": 0.88,
                    "source_metrics": ["profiler"],
                    "explanation": "Colors show correlation strength. Darker reds represent strong positive correlations.",
                    "expected_insight": "Identify redundant pairs (correlation > 0.8 or < -0.8).",
                    "rendering_config": {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "title": "Numeric Column Correlations",
                        "width": "container",
                        "height": 280,
                        "data": {"values": corr_records},
                        "mark": "rect",
                        "encoding": {
                            "x": {"field": "var1", "type": "nominal", "title": ""},
                            "y": {"field": "var2", "type": "nominal", "title": ""},
                            "color": {"field": "correlation", "type": "quantitative", "scale": {"scheme": "redblue", "domain": [-1, 1]}}
                        }
                    }
                })
            except Exception as e:
                logger.warning("Failed to construct correlation heatmap matrix: %s", e)

        # 5. Quality Visualization (Missing Value Ratio)
        null_counts = df.isnull().sum()
        missing_data = []
        for col in df.columns:
            s_name = pii_mapping.get(col, col)
            null_pct = float((null_counts[col] / len(df)) * 100)
            if null_pct > 0:
                missing_data.append({"column": s_name, "null_percentage": round(null_pct, 2)})

        if missing_data:
            # Sort by null percentage descending
            missing_data = sorted(missing_data, key=lambda x: x["null_percentage"], reverse=True)
            candidates.append({
                "visualization_id": str(uuid.uuid4()),
                "chart_type": "quality_chart",
                "columns": [x["column"] for x in missing_data],
                "title": "Missing Value Rates by Feature",
                "description": "Bar chart demonstrating percentage rates of missing cells across columns.",
                "business_reason": "Flags key attributes that need imputation before ingestion.",
                "confidence_score": 0.95,
                "source_metrics": ["quality"],
                "explanation": "The height of each column indicates the percentage of missing observations.",
                "expected_insight": "Isolate variables with high null rates (> 15%) for selective drop strategies.",
                "rendering_config": {
                    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                    "title": "Missing Value Percentages",
                    "width": "container",
                    "height": 280,
                    "data": {"values": missing_data},
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "column", "type": "nominal", "sort": "-y", "title": "Feature Column"},
                        "y": {"field": "null_percentage", "type": "quantitative", "title": "Missing Ratio (%)"}
                    }
                }
            })

        return candidates, sampled_records

    def _build_prompt(self, profile: Dict[str, Any], quality: Dict[str, Any], candidates: List[Dict[str, Any]], persona: str) -> str:
        """Construct prompt grounded strictly in statistical aggregates."""
        prompt_lines = [
            "You are a Visualization Expert. Enhance the descriptions and narrative interpretations of the candidate charts.",
            "You must ground your descriptions strictly in the provided metadata. Do not change columns or chart configurations.",
            "Rules:",
            "1. Output a JSON array containing text enhancements mapping to the visualization_id of the candidate charts.",
            "2. For each element, supply: visualization_id, title, description, business_reason, expected_insight, and explanation.",
            "3. Format your output by writing any overall summaries first, followed by the tag '[INSIGHTS_JSON_START]', and then a single JSON array containing the enhanced objects.",
            "Example:",
            "Visualizations analysis summary...",
            "[INSIGHTS_JSON_START]",
            "[",
            "  {",
            '    "visualization_id": "uuid_provided_below",',
            '    "title": "Distribution of Customer Age",',
            '    "description": "Histogram mapping the age categories of churn segments.",',
            '    "business_reason": "Determines the core demographics target range.",',
            '    "expected_insight": "Peak customer age lies in the 30-35 range.",',
            '    "explanation": "The x-axis displays age bins, and the y-axis shows user counts."...',
            "  }",
            "]",
            "\nDataset Metadata:",
            f"Shape: {profile.get('rows')} rows x {profile.get('columns')} columns",
            f"Numerical statistics: {profile.get('numerical_stats')}",
            f"Quality Issues: {quality.get('issues')}",
            "\nCandidate Visualizations to Enhance:"
        ]

        for cand in candidates:
            prompt_lines.append(
                f"- ID: {cand['visualization_id']} | Type: {cand['chart_type']} | "
                f"Columns: {cand['columns']} | Fallback Title: {cand['title']}"
            )

        prompt_lines.append(f"\nUser context/persona: {persona}")
        return "\n".join(prompt_lines)

    def _parse_llm_response(self, content: str) -> Dict[str, Dict[str, Any]]:
        """Parse JSON array output after [INSIGHTS_JSON_START] tag into dict index."""
        if "[INSIGHTS_JSON_START]" in content:
            parts = content.split("[INSIGHTS_JSON_START]")
            json_str = parts[1].strip()
            
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            try:
                items = json.loads(json_str)
                if isinstance(items, list):
                    mapping = {}
                    for item in items:
                        if isinstance(item, dict) and "visualization_id" in item:
                            mapping[item["visualization_id"]] = item
                    return mapping
            except Exception as e:
                logger.warning("Failed to parse LLM visualizations JSON: %s. Content: %s", e, json_str)
        return {}


# Singleton dependency resolver
_visualization_service_instance = None

def get_visualization_service() -> VisualizationService:
    """Factory dependency resolver for Auto Visualization Generator service layer."""
    global _visualization_service_instance
    if _visualization_service_instance is None:
        _visualization_service_instance = VisualizationService()
    return _visualization_service_instance
