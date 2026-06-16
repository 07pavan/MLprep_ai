import pytest
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager
from config.settings import settings

client = TestClient(app)

@pytest.fixture
def mock_auth():
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_viz_user"}
    yield
    app.dependency_overrides = {}
    settings.ENABLE_AUTH = orig_enable_auth

@pytest.fixture
def test_session():
    uid = "test_viz_user"
    session_id = session_manager.create_session(uid)
    # 10 rows to trigger all visual types (e.g. outlier check, correlation metrics, null checks)
    df = pd.DataFrame({
        "customer_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "category_low": ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"], 
        "category_high": ["X", "Y", "Z", "W", "V", "U", "T", "S", "R", "Q"], 
        "age": [25, 30, 35, 40, 45, 50, 55, 120, 33, 41], 
        "salary": [50000, 60000, 70000, 80000, 90000, 100000, 110000, 250000, 71000, 82000], 
        "date_joined": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10"]), 
        "score": [9.5, 8.0, 7.5, None, 9.0, 8.5, 9.2, 8.8, 7.9, 9.1]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

@patch("services.visualization_service.get_llm")
def test_api_visualization_success(mock_get_llm, mock_auth, test_session):
    """Test successful visualization generation API call with LLM mocks."""
    mock_llm = MagicMock()
    
    def mock_invoke(prompt):
        # Extract ID from prompt if possible
        import re
        match = re.search(r"- ID: ([a-f0-9\-]+)", prompt)
        viz_id = match.group(1) if match else "some-fallback-id"
        
        mock_response = MagicMock()
        mock_response.content = f"""
        Here is the analysis.
        [INSIGHTS_JSON_START]
        [
          {{
            "visualization_id": "{viz_id}",
            "title": "LLM Enhanced Title",
            "description": "LLM Enhanced Description",
            "business_reason": "LLM Enhanced Business Reason",
            "expected_insight": "LLM Enhanced Expected Insight",
            "explanation": "LLM Enhanced Explanation"
          }}
        ]
        """
        return mock_response

    mock_llm.invoke.side_effect = mock_invoke
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "visualizationType": "distribution",
        "persona": "general"
    }

    res = client.post("/api/v3/visualizations/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["visualizations"]) >= 1
    
    # Check that LLM enhancements got merged
    first_item = data["visualizations"][0]
    assert first_item["title"] == "LLM Enhanced Title"
    assert first_item["description"] == "LLM Enhanced Description"
    assert data["metadata"]["total_recommendations"] > 0

def test_api_visualization_invalid_type(mock_auth, test_session):
    """Test API rejects unsupported or invalid visualizationType with 400 Bad Request."""
    payload = {
        "sessionId": test_session,
        "visualizationType": "invalid_type_here",
        "persona": "general"
    }
    res = client.post("/api/v3/visualizations/generate", json=payload)
    assert res.status_code == 400
    assert "invalid visualizationtype" in res.json()["detail"].lower()

def test_api_visualization_unauthorized(test_session):
    """Test API rejects queries missing auth tokens with 401."""
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides = {}

    try:
        payload = {
            "sessionId": test_session,
            "visualizationType": "general"
        }
        res = client.post("/api/v3/visualizations/generate", json=payload)
        # Note: Depending on security middleware, missing token returns 401
        assert res.status_code == 401
    finally:
        settings.ENABLE_AUTH = orig_enable_auth

def test_api_visualization_cross_user_isolation(mock_auth, test_session):
    """Test API rejects requests to other users' sessions with 404 (isolation)."""
    # Authenticate as a different user
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "malicious_user"}

    payload = {
        "sessionId": test_session,
        "visualizationType": "general"
    }
    res = client.post("/api/v3/visualizations/generate", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

def test_api_visualization_missing_session(mock_auth):
    """Test API returns 404 for missing sessions."""
    payload = {
        "sessionId": "non-existent-session-uuid",
        "visualizationType": "general"
    }
    res = client.post("/api/v3/visualizations/generate", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

@patch("services.visualization_service.get_llm")
def test_api_visualization_fallback_on_llm_failure(mock_get_llm, mock_auth, test_session):
    """Test API serves fallback visualization specs if LLM generates exceptions."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM failure")
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "visualizationType": "general"
    }
    res = client.post("/api/v3/visualizations/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["visualizations"]) >= 1
    
    # Assert fallback attributes are present and filled
    first_item = data["visualizations"][0]
    assert len(first_item["title"]) > 0
    assert len(first_item["description"]) > 0
    assert len(first_item["business_reason"]) > 0
