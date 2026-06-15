from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class VisualizationItem(BaseModel):
    visualization_id: str
    chart_type: str = Field(description="One of: bar, pie, line, histogram, scatter, box, heatmap, quality_chart")
    columns: List[str] = Field(default_factory=list)
    title: str
    description: str
    business_reason: str
    confidence_score: float
    source_metrics: List[str] = Field(default_factory=list)
    rendering_config: Dict[str, Any] = Field(default_factory=dict, description="Vega-Lite specification or parameters")
    explanation: Optional[str] = None
    expected_insight: Optional[str] = None

class VisualizationRecommendRequest(BaseModel):
    sessionId: str
    persona: str = "general"

class VisualizationRecommendResponse(BaseModel):
    success: bool
    recommendations: List[VisualizationItem] = Field(default_factory=list)
    error: Optional[str] = None

class VisualizationGenerateRequest(BaseModel):
    sessionId: str
    visualizationType: str = "general" # general, distribution, categorical, correlation, time_series, quality
    persona: str = "general"

class VisualizationGenerateResponse(BaseModel):
    success: bool
    visualizations: List[VisualizationItem] = Field(default_factory=list)
    confidenceScores: Dict[str, float] = Field(default_factory=dict)
    explanations: Dict[str, str] = Field(default_factory=dict)
    sourceMetrics: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
