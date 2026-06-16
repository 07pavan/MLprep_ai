import pytest
import os
import pandas as pd
from unittest.mock import MagicMock, patch

from schemas.visualization import VisualizationItem, VisualizationRecommendRequest, VisualizationRecommendResponse
from services.visualization_service import (
    VisualizationService,
    get_visualization_service
)
from utils.session_manager import session_manager

@pytest.fixture
def test_session():
    uid = "test_viz_user"
    session_id = session_manager.create_session(uid)
    # Include numeric, low-cardinality, and high-cardinality categorical variables, datetime, and null values
    df = pd.DataFrame({
        "customer_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "category_low": ["A", "B", "A", "B", "A", "B", "A", "B"], 
        "category_high": ["X", "Y", "Z", "W", "V", "U", "T", "S"], 
        "age": [25, 30, 35, 40, 45, 50, 55, 120], 
        "salary": [50000, 60000, 70000, 80000, 90000, 100000, 110000, 250000], 
        "date_joined": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]), 
        "score": [9.5, 8.0, 7.5, None, 9.0, 8.5, 9.2, 8.8]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

def test_schemas_validation():
    # Request validation
    req = VisualizationRecommendRequest(
        sessionId="session_abc",
        persona="finance"
    )
    assert req.sessionId == "session_abc"
    assert req.persona == "finance"

    # Item validation
    item = VisualizationItem(
        visualization_id="viz_123",
        chart_type="line",
        columns=["date", "value"],
        title="Trend over Time",
        description="Line chart description...",
        business_reason="Trace changes.",
        confidence_score=0.95,
        source_metrics=["profiler"],
        rendering_config={"mark": "line", "encoding": {"x": {"field": "date"}}}
    )
    assert item.visualization_id == "viz_123"

    # Response validation
    res = VisualizationRecommendResponse(
        success=True,
        recommendations=[item]
    )
    assert res.success is True
    assert len(res.recommendations) == 1

@patch("services.visualization_service.get_llm")
def test_visualization_llm_success(mock_get_llm, test_session):
    """Test LLM-enhanced descriptions are merged into recommendations correctly."""
    uid = "test_viz_user"
    mock_llm = MagicMock()
    
    def mock_invoke(prompt):
        import re
        match = re.search(r"- ID: ([a-f0-9\-]+)", prompt)
        viz_id = match.group(1) if match else "some-fallback-id"
        
        mock_response = MagicMock()
        mock_response.content = f"""
        Here is the analysis of visualizations.
        [INSIGHTS_JSON_START]
        [
          {{
            "visualization_id": "{viz_id}",
            "title": "Enhanced Distribution of Age",
            "description": "Enhanced description detail...",
            "business_reason": "Enhanced business reason...",
            "expected_insight": "Enhanced expected insight...",
            "explanation": "Enhanced explanation..."
          }}
        ]
        """
        return mock_response

    mock_llm.invoke.side_effect = mock_invoke
    mock_get_llm.return_value = mock_llm

    service = VisualizationService()
    res = service.get_recommendations(uid, test_session, "general")
    assert res["success"] is True
    assert len(res["recommendations"]) >= 1

    # Check that LLM enhancements are correctly merged for target viz
    # The first item should be our enhanced one since its ID will match the one we parsed
    first_item = res["recommendations"][0]
    assert first_item["title"] == "Enhanced Distribution of Age"
    assert first_item["description"] == "Enhanced description detail..."
    assert first_item["explanation"] == "Enhanced explanation..."

@patch("services.visualization_service.get_llm")
def test_visualization_llm_failure_fallback(mock_get_llm, test_session):
    uid = "test_viz_user"
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM connection drop")
    mock_get_llm.return_value = mock_llm

    service = get_visualization_service()
    res = service.get_recommendations(uid, test_session, "general")

    # Success should still be true through fallback
    assert res["success"] is True
    assert len(res["recommendations"]) >= 1
    
    # Ensure descriptions and titles are still filled
    first_item = res["recommendations"][0]
    assert len(first_item["title"]) > 0
    assert len(first_item["description"]) > 0
    assert len(first_item["business_reason"]) > 0

@patch("services.visualization_service.get_llm")
def test_chart_selection_rules(mock_get_llm, test_session):
    uid = "test_viz_user"
    mock_get_llm.return_value = None  # Force fallback logic

    service = VisualizationService()
    res = service.get_recommendations(uid, test_session)
    
    chart_types = [item["chart_type"] for item in res["recommendations"]]
    
    # 1. Distribution: histogram and box plot should be selected for 'age' / 'salary'
    assert "histogram" in chart_types
    assert "box" in chart_types

    # 2. Category: pie chart (cardinality 2) and bar chart (cardinality 6) should be selected
    assert "pie" in chart_types
    assert "bar" in chart_types

    # 3. Time Series: line chart should be selected for 'date_joined' + numeric
    assert "line" in chart_types

    # 4. Correlation: scatter and heatmap should be selected for numeric columns
    assert "scatter" in chart_types
    assert "heatmap" in chart_types

    # 5. Quality chart: missing value chart should be selected since 'score' has null
    assert "quality_chart" in chart_types

    # 6. Verify rendering configurations
    for item in res["recommendations"]:
        spec = item["rendering_config"]
        assert spec["$schema"] == "https://vega.github.io/schema/vega-lite/v5.json"
        assert "mark" in spec
        assert "encoding" in spec

def test_non_existent_session_raises_exception():
    service = VisualizationService()
    with pytest.raises(Exception):
        service.get_recommendations("test_viz_user", "missing-session-uuid")

@patch("services.visualization_service.get_llm")
def test_visualization_cache_hits(mock_get_llm, test_session):
    uid = "test_viz_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Summary [INSIGHTS_JSON_START] []"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = VisualizationService()

    # First call: LLM invoked
    res_1 = service.get_recommendations(uid, test_session)
    assert mock_llm.invoke.call_count == 1

    # Second call: Cache reuse, LLM not invoked again
    res_2 = service.get_recommendations(uid, test_session)
    assert mock_llm.invoke.call_count == 1
    assert len(res_2["recommendations"]) == len(res_1["recommendations"])
