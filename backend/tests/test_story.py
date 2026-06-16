import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from schemas.story import StoryReportResponse, ExecutiveSummaryModel, ReportSection, ReportRecommendationItem
from services.story_service import StorytellingService, get_story_service
from utils.session_manager import session_manager

@pytest.fixture
def test_session():
    uid = "test_story_user"
    session_id = session_manager.create_session(uid)
    df = pd.DataFrame({
        "customer_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "category_low": ["A", "B", "A", "B", "A", "B", "A", "B"], 
        "age": [25, 30, 35, 40, 45, 50, 55, 120], 
        "salary": [50000, 60000, 70000, 80000, 90000, 100000, 110000, 250000],
        "score": [9.5, 8.0, 7.5, None, 9.0, 8.5, 9.2, 8.8]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

def test_story_schemas_validation():
    summary = ExecutiveSummaryModel(
        dataset_overview="Dataset containing customer salary profiles.",
        data_quality_score=92.5,
        overall_business_summary="The business exhibits positive scaling trends."
    )
    section = ReportSection(
        section_id="key_findings",
        title="Key Findings",
        content="Narrative content...",
        metadata={"columns": ["age", "salary"]}
    )
    rec = ReportRecommendationItem(
        rec_type="business",
        title="Optimize conversion funnel",
        description="Verify age brackets.",
        expected_impact="High conversion rate.",
        action_steps=["Audit database entries"]
    )
    report = StoryReportResponse(
        report_id="rep_123",
        title="Executive Report",
        executive_summary=summary,
        sections=[section],
        recommendations=[rec],
        confidence_score=0.95,
        sources=["profiler", "quality"],
        generated_timestamp="2026-06-14T23:27:55"
    )
    assert report.report_id == "rep_123"
    assert report.executive_summary.data_quality_score == 92.5
    assert len(report.sections) == 1

@patch("services.story_service.get_llm")
def test_story_generation_llm_success(mock_get_llm, test_session):
    uid = "test_story_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    Here is the story analysis.
    [STORY_JSON_START]
    {
      "report_id": "rep-uuid-9999",
      "title": "LLM Generated Story Report",
      "executive_summary": {
        "dataset_overview": "Overview of customer parameters.",
        "data_quality_score": 90.0,
        "overall_business_summary": "LLM overall summary details."
      },
      "sections": [
        {
          "section_id": "key_findings",
          "title": "LLM Section Findings",
          "content": "LLM text content details.",
          "metadata": {}
        }
      ],
      "recommendations": [
        {
          "rec_type": "business",
          "title": "Optimize operations",
          "description": "Adjust settings.",
          "expected_impact": "High efficiency.",
          "action_steps": ["Step 1"]
        }
      ],
      "confidence_score": 0.95,
      "sources": ["profiler", "quality"],
      "generated_timestamp": "2026-06-14T23:27:55"
    }
    """
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = StorytellingService()
    res = service.generate_story_report(uid, test_session, "executive")

    assert res["success"] is True
    assert res["report"]["report_id"] == "rep-uuid-9999"
    assert res["report"]["title"] == "LLM Generated Story Report"
    assert res["metadata"]["is_fallback"] is False

@patch("services.story_service.get_llm")
def test_story_generation_llm_failure_fallback(mock_get_llm, test_session):
    uid = "test_story_user"
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("Groq connection timeout")
    mock_get_llm.return_value = mock_llm

    service = StorytellingService()
    res = service.generate_story_report(uid, test_session, "general")

    # Success should still be true through the local fallback generator
    assert res["success"] is True
    assert res["metadata"]["is_fallback"] is True
    
    # Assert fallback attributes are correctly populated and non-empty
    report = res["report"]
    assert len(report["report_id"]) > 0
    assert report["title"].startswith("Executive Data Storytelling Report")
    assert report["executive_summary"]["data_quality_score"] > 0.0
    assert len(report["sections"]) >= 4
    assert len(report["recommendations"]) >= 3

@patch("services.story_service.get_llm")
def test_story_pii_protection(mock_get_llm, test_session):
    """Verify that columns with PII identifiers are sanitized before LLM transmission."""
    uid = "test_story_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "[STORY_JSON_START] {}"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    # Re-save dataframe with clear PII headers: e.g. customer_name, email_address
    df_pii = pd.DataFrame({
        "customer_name": ["Alice", "Bob"],
        "email_address": ["alice@gmail.com", "bob@gmail.com"],
        "age": [25, 30]
    })
    session_manager.save_dataframe(uid, test_session, df_pii)

    service = StorytellingService()
    # Execute generation, which invokes building the prompt
    service.generate_story_report(uid, test_session)

    # Inspect the prompt string passed to LLM invoke
    assert mock_llm.invoke.call_count == 1
    prompt_sent = mock_llm.invoke.call_args[0][0]
    
    # Assert raw PII header labels are masked
    assert "customer_name" not in prompt_sent
    assert "email_address" not in prompt_sent
    assert "[ANONYMIZED_PII_" in prompt_sent

@patch("services.story_service.get_llm")
def test_story_caching(mock_get_llm, test_session):
    uid = "test_story_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    [STORY_JSON_START]
    {
      "report_id": "cached-uuid",
      "title": "Cached Report",
      "executive_summary": {
        "dataset_overview": "Overview info.",
        "data_quality_score": 85.0,
        "overall_business_summary": "Summary details."
      },
      "sections": [],
      "recommendations": [],
      "confidence_score": 0.85,
      "sources": [],
      "generated_timestamp": "2026"
    }
    """
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = StorytellingService()
    
    # First call - LLM invoked
    res1 = service.generate_story_report(uid, test_session)
    assert mock_llm.invoke.call_count == 1

    # Second call - cache hit, LLM count remains 1
    res2 = service.generate_story_report(uid, test_session)
    assert mock_llm.invoke.call_count == 1
    assert res1["report"]["report_id"] == res2["report"]["report_id"]

def test_non_existent_session_raises_exception():
    service = get_story_service()
    with pytest.raises(Exception):
        service.generate_story_report("test_story_user", "invalid-session-uuid")
