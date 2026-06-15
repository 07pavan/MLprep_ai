from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class InsightItem(BaseModel):
    insight_id: str
    category: str = Field(description="One of: statistical, quality, ml_readiness, business")
    title: str
    description: str
    severity: str = Field(description="One of: HIGH, MEDIUM, LOW")
    confidence_score: float
    source_metrics: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)

class InsightsRequest(BaseModel):
    sessionId: str
    insightType: str = "general"  # mapping to general, statistical, quality, ml_readiness, business
    persona: str = "general"

class InsightsResponse(BaseModel):
    success: bool
    insights: List[InsightItem] = Field(default_factory=list)
    confidence: float = 0.85
    sources: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

