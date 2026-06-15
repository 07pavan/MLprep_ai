from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ExecutiveSummaryModel(BaseModel):
    dataset_overview: str = Field(description="Aggregated metadata description of columns and record counts.")
    data_quality_score: float = Field(description="Aggregated data quality rating from 0 to 100.")
    overall_business_summary: str = Field(description="Summary narrative explaining business highlights and core conclusions.")

class ReportSection(BaseModel):
    section_id: str = Field(description="Unique string matching: key_findings, visualization_summary, data_quality, ml_readiness.")
    title: str = Field(description="Descriptive header for the section.")
    content: str = Field(description="Detailed narrative commentary for the section.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Related attributes, columns list, or visualization associations.")

class ReportRecommendationItem(BaseModel):
    rec_type: str = Field(description="Category of suggestion. Must be one of: business, analytical, ml.")
    title: str = Field(description="Clear title of the action step.")
    description: str = Field(description="Detailed explanation of the issue and fix.")
    expected_impact: str = Field(description="Quantifiable or narrative benefit of execution.")
    action_steps: List[str] = Field(default_factory=list, description="Sequence of individual operations to perform.")

class StoryReportResponse(BaseModel):
    report_id: str = Field(description="Unique report UUID.")
    title: str = Field(description="Narrative business title of the report.")
    executive_summary: ExecutiveSummaryModel = Field(description="Overall dataset summary and general metrics.")
    sections: List[ReportSection] = Field(default_factory=list, description="Sectioned report bodies.")
    recommendations: List[ReportRecommendationItem] = Field(default_factory=list, description="Action items for analysts and developers.")
    confidence_score: float = Field(description="Overall confidence weight from 0.0 to 1.0.")
    sources: List[str] = Field(default_factory=list, description="Underlying tool or metadata inputs involved.")
    generated_timestamp: str = Field(description="ISO 8601 creation timestamp.")

class StoryGenerateRequest(BaseModel):
    sessionId: str
    reportType: str = "executive" # executive, technical, business, ML readiness
    persona: str = "general"

class StoryGenerateResponse(BaseModel):
    success: bool
    report: Optional[StoryReportResponse] = None
    confidence_score: float = Field(default=0.85, alias="confidenceScore")
    sources: List[str] = Field(default_factory=list, alias="sourceMetadata")
    generated_timestamp: Optional[str] = Field(default=None, alias="generatedTimestamp")
    errors: List[str] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True
    }
