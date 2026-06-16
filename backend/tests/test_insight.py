import pytest
import os
import pandas as pd
from unittest.mock import MagicMock, patch

from schemas.insight import InsightItem, InsightsRequest, InsightsResponse
from services.insight_service import (
    InsightService,
    get_insight_service
)
from utils.session_manager import session_manager

@pytest.fixture
def test_session():
    uid = "test_insight_user"
    session_id = session_manager.create_session(uid)
    # DataFrame containing normal columns and PII-like columns
    df = pd.DataFrame({
        "customer_id": [1, 2, 3],
        "customer_email": ["a@example.com", "b@example.com", "c@example.com"],
        "phone_number": ["123", "456", "789"],
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

def test_schemas_validation():
    # Valid Request
    req = InsightsRequest(
        sessionId="session_abc",
        insightType="statistical",
        persona="general"
    )
    assert req.sessionId == "session_abc"
    assert req.insightType == "statistical"
    assert req.persona == "general"

    # Valid Response
    item = InsightItem(
        insight_id="ins_123",
        category="statistical",
        title="High Variance",
        description="Salary column has high variance.",
        severity="MEDIUM",
        confidence_score=0.90,
        source_metrics=["profiler"],
        recommended_actions=["Review variance."]
    )
    res = InsightsResponse(
        success=True,
        insights=[item],
        confidence=0.90,
        sources=["profiler"],
        metadata={"summary": "Overview of data."},
        error=None
    )
    assert res.success is True
    assert len(res.insights) == 1
    assert res.insights[0].insight_id == "ins_123"

@patch("services.insight_service.get_llm")
def test_insights_llm_success(mock_get_llm, test_session):
    uid = "test_insight_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    
    # Return formatted summary and a valid JSON block of insights
    mock_response.content = """
    This is an overall summary of customer metadata.
    [INSIGHTS_JSON_START]
    [
      {
        "insight_id": "test_uuid_123",
        "category": "statistical",
        "title": "Salary Distribution Skew",
        "description": "Salary values demonstrate standard right-hand statistical skewness.",
        "severity": "HIGH",
        "confidence_score": 0.95,
        "source_metrics": ["profiler"],
        "recommended_actions": ["Impute extreme elements."]
      },
      {
        "insight_id": "test_uuid_456",
        "category": "quality",
        "title": "PII Exposure Warning",
        "description": "Column phone_number contains potential contact details.",
        "severity": "MEDIUM",
        "confidence_score": 0.88,
        "source_metrics": ["quality"],
        "recommended_actions": ["Anonymize column during next cleaning plan."]
      }
    ]
    """
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = get_insight_service()
    res = service.generate_insights(uid, test_session, category="all", min_severity="LOW")

    assert res["success"] is True
    assert "overall summary" in res["metadata"]["summary"]
    assert len(res["insights"]) == 2
    assert res["insights"][0]["title"] == "Salary Distribution Skew"
    assert res["insights"][0]["severity"] == "HIGH"
    assert res["insights"][1]["category"] == "quality"

@patch("services.insight_service.get_llm")
def test_insights_llm_failure_fallback(mock_get_llm, test_session):
    uid = "test_insight_user"
    # Force exception on LLM call to test deterministic fallback triggers
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM timed out")
    mock_get_llm.return_value = mock_llm

    service = InsightService()
    res = service.generate_insights(uid, test_session, category="all", min_severity="LOW")

    # Success should still be true through fallback
    assert res["success"] is True
    assert "Deterministic statistical insight" in res["metadata"]["summary"]
    assert len(res["insights"]) >= 1
    
    # Check that fallback statistical and readiness insights are present
    categories = [item["category"] for item in res["insights"]]
    assert "statistical" in categories
    assert "ml_readiness" in categories

@patch("services.insight_service.get_llm")
def test_insights_category_and_severity_filtering(mock_get_llm, test_session):
    uid = "test_insight_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    Mock dataset summary.
    [INSIGHTS_JSON_START]
    [
      {
        "insight_id": "i1",
        "category": "statistical",
        "title": "Stats Low",
        "description": "Desc",
        "severity": "LOW",
        "confidence_score": 0.90,
        "source_metrics": ["profiler"],
        "recommended_actions": []
      },
      {
        "insight_id": "i2",
        "category": "quality",
        "title": "Quality High",
        "description": "Desc",
        "severity": "HIGH",
        "confidence_score": 0.95,
        "source_metrics": ["quality"],
        "recommended_actions": []
      },
      {
        "insight_id": "i3",
        "category": "ml_readiness",
        "title": "ML Medium",
        "description": "Desc",
        "severity": "MEDIUM",
        "confidence_score": 0.85,
        "source_metrics": ["ml_readiness"],
        "recommended_actions": []
      }
    ]
    """
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = InsightService()

    # 1. Category Filter: statistical only
    res_stats = service.generate_insights(uid, test_session, category="statistical", min_severity="LOW")
    assert len(res_stats["insights"]) == 1
    assert res_stats["insights"][0]["category"] == "statistical"

    # 2. Severity Filter: MEDIUM and above (should return Quality High and ML Medium, but exclude Stats Low)
    res_sev = service.generate_insights(uid, test_session, category="all", min_severity="MEDIUM")
    assert len(res_sev["insights"]) == 2
    sevs = [item["severity"] for item in res_sev["insights"]]
    assert "LOW" not in sevs
    assert "HIGH" in sevs
    assert "MEDIUM" in sevs

def test_non_existent_session_raises_exception():
    service = InsightService()
    # Querying a non-existent session should raise FileNotFoundError or similar
    with pytest.raises(Exception):
        service.generate_insights("test_insight_user", "missing-session-123")

@patch("services.insight_service.get_llm")
def test_insights_cache_hits(mock_get_llm, test_session):
    uid = "test_insight_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Summary [INSIGHTS_JSON_START] []"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = InsightService()

    # First call: LLM invoked
    res_1 = service.generate_insights(uid, test_session)
    assert mock_llm.invoke.call_count == 1

    # Second call: Cache reuse, LLM not invoked again
    res_2 = service.generate_insights(uid, test_session)
    assert mock_llm.invoke.call_count == 1
    assert res_2["metadata"]["summary"] == res_1["metadata"]["summary"]
