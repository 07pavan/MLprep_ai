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
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_explanation_user"}
    yield
    app.dependency_overrides = {}
    settings.ENABLE_AUTH = orig_enable_auth

@pytest.fixture
def test_session():
    uid = "test_explanation_user"
    session_id = session_manager.create_session(uid)
    df = pd.DataFrame({
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000],
        "dept": ["IT", "HR", "IT"]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

@patch("services.explanation_service.get_llm")
def test_api_explain_success(mock_get_llm, mock_auth, test_session):
    """Test successful dataset explanation call with mocked LLM."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "API Success Summary [INSIGHTS_START]\n- API Insight 1\n- API Insight 2"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "aspect": "profiling",
        "persona": "general"
    }

    res = client.post("/api/v3/explanation/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["summary"] == "API Success Summary"
    assert "API Insight 1" in data["insights"]
    assert "API Insight 2" in data["insights"]
    assert data["confidence"] == 0.90
    assert "profiler" in data["sources"]
    assert "profiling" in data["raw_metrics"]
    assert data["error"] is None

@patch("services.explanation_service.get_llm")
def test_api_explain_fallback_on_llm_failure(mock_get_llm, mock_auth, test_session):
    """Test API fallback triggers deterministic analysis when LLM fails."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM failure")
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "aspect": "profiling"
    }

    res = client.post("/api/v3/explanation/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "contains 3 rows" in data["summary"]
    assert data["confidence"] == 0.70
    assert "profiler" in data["sources"]
    assert "profiling" in data["raw_metrics"]
    assert data["error"] is None

def test_api_explain_unauthorized(test_session):
    """Test endpoint rejects queries if authorization token is absent/invalid."""
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides = {}

    try:
        payload = {
            "sessionId": test_session,
            "aspect": "general"
        }
        res = client.post("/api/v3/explanation/explain", json=payload)
        assert res.status_code == 401
    finally:
        settings.ENABLE_AUTH = orig_enable_auth

def test_api_explain_cross_user_isolation(mock_auth, test_session):
    """Test tenant isolation rejects explanation request for another user's session."""
    # Authenticate as attacker
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "attacker_user"}

    payload = {
        "sessionId": test_session,
        "aspect": "general"
    }
    res = client.post("/api/v3/explanation/explain", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

def test_api_explain_non_existent_session(mock_auth):
    """Test 404 is returned when session ID is missing or incorrect."""
    payload = {
        "sessionId": "missing-session-abc",
        "aspect": "general"
    }
    res = client.post("/api/v3/explanation/explain", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

@patch("services.explanation_service.get_llm")
def test_api_explain_invalid_aspect_graceful(mock_get_llm, mock_auth, test_session):
    """Test invalid aspect falls back to general-style description gracefully."""
    mock_get_llm.return_value = None

    payload = {
        "sessionId": test_session,
        "aspect": "invalid_aspect"
    }
    res = client.post("/api/v3/explanation/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "General overview of dataset" in data["summary"]
    assert data["confidence"] == 0.70
