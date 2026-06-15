from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ExplanationRequest(BaseModel):
    sessionId: str
    aspect: str = Field(description="One of: general, profiling, quality, ml_readiness, cleaning_history")
    persona: str = "general"

class ExplanationResponse(BaseModel):
    success: bool
    summary: str
    insights: List[str] = Field(default_factory=list)
    confidence: float
    sources: List[str] = Field(default_factory=list)
    raw_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
