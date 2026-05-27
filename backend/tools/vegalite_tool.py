"""Vega-Lite specification generator, validator, and rule-based fallback"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class VegaLiteTool:
    """Generate, validate, and fall back on Vega-Lite v5 JSON specs."""

    SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"

    # ------------------------------------------------------------------
    # Tier 1 — keyword rule-based generation
    # ------------------------------------------------------------------

    def generate_spec_from_rules(
        self,
        df: pd.DataFrame,
        question: str,
        data_records: list[dict],
    ) -> Optional[dict]:
        """Return a Vega-Lite spec via keyword matching, or None."""
        q = question.lower()

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        date_cols = df.select_dtypes(include="datetime64").columns.tolist()

        spec: Optional[dict] = None

        # ── Time-series / trend ───────────────────────────────────
        if any(w in q for w in ["trend", "over time", "time series", "timeline"]):
            if date_cols and numeric_cols:
                spec = self._base_spec(
                    f"Trend: {numeric_cols[0]} over {date_cols[0]}",
                    {"type": "line", "point": True},
                    x={"field": date_cols[0], "type": "temporal"},
                    y={"field": numeric_cols[0], "type": "quantitative"},
                )
            elif numeric_cols:
                spec = self._base_spec(
                    f"Trend: {numeric_cols[0]}",
                    {"type": "line", "point": True},
                    y={"field": numeric_cols[0], "type": "quantitative"},
                )

        # ── Distribution / histogram ──────────────────────────────
        elif any(w in q for w in ["distribution", "histogram", "spread", "frequency"]):
            if numeric_cols:
                spec = self._base_spec(
                    f"Distribution of {numeric_cols[0]}",
                    "bar",
                    x={"field": numeric_cols[0], "type": "quantitative", "bin": True},
                    y={"aggregate": "count", "type": "quantitative"},
                )

        # ── Comparison / bar ──────────────────────────────────────
        elif any(w in q for w in ["compare", "by", "group", "category", "highest", "lowest", "top", "ranking"]):
            if cat_cols and numeric_cols:
                spec = self._base_spec(
                    f"{numeric_cols[0]} by {cat_cols[0]}",
                    {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                    x={"field": cat_cols[0], "type": "nominal", "sort": "-y"},
                    y={"field": numeric_cols[0], "type": "quantitative", "aggregate": "sum"},
                    color={"field": cat_cols[0], "type": "nominal", "legend": None},
                )

        # ── Correlation / scatter ─────────────────────────────────
        elif any(w in q for w in ["correlation", "relationship", "vs", "versus", "scatter"]):
            if len(numeric_cols) >= 2:
                spec = self._base_spec(
                    f"{numeric_cols[0]} vs {numeric_cols[1]}",
                    {"type": "point", "filled": True, "opacity": 0.7},
                    x={"field": numeric_cols[0], "type": "quantitative"},
                    y={"field": numeric_cols[1], "type": "quantitative"},
                )

        # ── Pie / proportion ──────────────────────────────────────
        elif any(w in q for w in ["pie", "proportion", "share", "breakdown"]):
            if cat_cols and numeric_cols:
                spec = self._base_spec(
                    f"{numeric_cols[0]} share by {cat_cols[0]}",
                    {"type": "arc", "innerRadius": 50},
                    theta={"field": numeric_cols[0], "type": "quantitative", "aggregate": "sum"},
                    color={"field": cat_cols[0], "type": "nominal"},
                )

        if spec is not None:
            spec["data"] = {"values": data_records[:200]}
        return spec

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_spec(spec: dict) -> tuple[bool, str]:
        """Basic structural validation of a Vega-Lite spec."""
        if not isinstance(spec, dict):
            return False, "Spec must be a JSON object"
        if "mark" not in spec:
            return False, "Missing required key 'mark'"
        if "encoding" not in spec:
            return False, "Missing required key 'encoding'"
        enc = spec["encoding"]
        if not isinstance(enc, dict) or len(enc) == 0:
            return False, "Encoding must be a non-empty object"
        valid_channels = {"x", "y", "x2", "y2", "theta", "radius", "color", "size",
                          "shape", "opacity", "column", "row", "facet", "detail",
                          "tooltip", "text", "href", "url", "order", "angle"}
        enc_channels = set(enc.keys())
        if not enc_channels.intersection(valid_channels):
            return False, f"Encoding has no recognisable channels. Found: {enc_channels}"
        return True, "Valid"

    # ------------------------------------------------------------------
    # Tier 3 — failsafe fallback
    # ------------------------------------------------------------------

    def build_fallback_spec(
        self, df: pd.DataFrame, data_records: list[dict]
    ) -> dict:
        """Always returns a valid spec, no matter what."""
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include="object").columns.tolist()

        if cat_cols and numeric_cols:
            spec = self._base_spec(
                f"Overview: {numeric_cols[0]} by {cat_cols[0]}",
                {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                x={"field": cat_cols[0], "type": "nominal", "sort": "-y"},
                y={"field": numeric_cols[0], "type": "quantitative", "aggregate": "sum"},
                color={"field": cat_cols[0], "type": "nominal", "legend": None},
            )
        elif len(numeric_cols) >= 2:
            spec = self._base_spec(
                f"Overview: {numeric_cols[0]} vs {numeric_cols[1]}",
                {"type": "point", "filled": True},
                x={"field": numeric_cols[0], "type": "quantitative"},
                y={"field": numeric_cols[1], "type": "quantitative"},
            )
        elif numeric_cols:
            spec = self._base_spec(
                f"Distribution of {numeric_cols[0]}",
                "bar",
                x={"field": numeric_cols[0], "type": "quantitative", "bin": True},
                y={"aggregate": "count", "type": "quantitative"},
            )
        else:
            # last resort — text table
            first_col = df.columns[0] if len(df.columns) > 0 else "index"
            spec = self._base_spec(
                "Data Preview",
                "text",
                x={"field": first_col, "type": "nominal"},
                text={"field": first_col, "type": "nominal"},
            )

        spec["data"] = {"values": data_records[:200]}
        return spec

    # ------------------------------------------------------------------
    # Helpers for parsing LLM output
    # ------------------------------------------------------------------

    @staticmethod
    def extract_json(text: str) -> Optional[dict]:
        """Extract a JSON object from LLM text, stripping markdown fences."""
        text = text.strip()

        # Strip ```json ... ``` or ``` ... ```
        import re
        m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find the first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        return None

    # ------------------------------------------------------------------
    # Private base spec builder
    # ------------------------------------------------------------------

    def _base_spec(self, title: str, mark: Any, **encoding_channels) -> dict:
        """Build a base Vega-Lite v5 spec dict with common defaults."""
        spec = {
            "$schema": self.SCHEMA,
            "title": title,
            "width": "container",
            "height": 350,
            "mark": mark,
            "encoding": {},
        }
        for channel, definition in encoding_channels.items():
            if isinstance(definition, dict):
                # Add tooltip by default if x and y are present
                spec["encoding"][channel] = definition
        return spec
