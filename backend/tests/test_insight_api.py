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
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_insight_user"}
    yield
    app.dependency_overrides = {}
    settings.ENABLE_AUTH = orig_enable_auth

@pytest.fixture
def test_session():
    uid = "test_insight_user"
    session_id = session_manager.create_session(uid)
    df = pd.DataFrame({
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000],
        "dept": ["IT", "HR", "IT"]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

@patch("services.insight_service.get_llm")
def test_api_insights_success(mock_get_llm, mock_auth, test_session):
    """Test successful proactive insights generation call via API."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    Proactive summary of transactional customer variables.
    [INSIGHTS_JSON_START]
    [
      {
        "insight_id": "i1",
        "category": "statistical",
        "title": "Skewness warning",
        "description": "Numerical features show minor skew.",
        "severity": "LOW",
        "confidence_score": 0.90,
        "source_metrics": ["profiler"],
        "recommended_actions": []
      }
    ]
    """
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "insightType": "statistical",
        "persona": "general"
    }

    res = client.post("/api/v3/insights/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["insights"]) == 1
    assert data["insights"][0]["title"] == "Skewness warning"
    assert data["confidence"] == 0.90
    assert "profiler" in data["sources"]
    assert "metadata" in data
    assert data["metadata"]["summary"] == "Proactive summary of transactional customer variables."
    assert data["error"] is None

def test_api_insights_invalid_type(mock_auth, test_session):
    """Test API rejects unsupported or invalid insightType with 400 Bad Request."""
    payload = {
        "sessionId": test_session,
        "insightType": "invalid_insight_type",
        "persona": "general"
    }
    res = client.post("/api/v3/insights/generate", json=payload)
    assert res.status_code == 400
    assert "invalid insighttype" in res.json()["detail"].lower()

def test_api_insights_unauthorized(test_session):
    """Test API rejects queries missing auth tokens with 401."""
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides = {}

    try:
        payload = {
            "sessionId": test_session,
            "insightType": "general"
        }
        res = client.post("/api/v3/insights/generate", json=payload)
        assert res.status_code == 401
    finally:
        settings.ENABLE_AUTH = orig_enable_auth

def test_api_insights_cross_user_isolation(mock_auth, test_session):
    """Test API rejects requests to other users' sessions with 404 (isolation)."""
    # Authenticate attacker
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "attacker_user"}

    payload = {
        "sessionId": test_session,
        "insightType": "general"
    }
    res = client.post("/api/v3/insights/generate", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

def test_api_insights_missing_session(mock_auth):
    """Test API returns 404 for missing sessions."""
    payload = {
        "sessionId": "missing-session-uuid",
        "insightType": "general"
    }
    res = client.post("/api/v3/insights/generate", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

@patch("services.insight_service.get_llm")
def test_api_insights_fallback_on_llm_failure(mock_get_llm, mock_auth, test_session):
    """Test API serves fallback statistical details if LLM generates exceptions."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM connection drop")
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "insightType": "general"
    }
    res = client.post("/api/v3/insights/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["insights"]) >= 1
    assert "Deterministic statistical insight" in data["metadata"]["summary"]
