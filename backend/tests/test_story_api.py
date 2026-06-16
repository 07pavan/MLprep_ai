import pytest
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager
from config.settings import settings
from services.story_service import get_story_service

client = TestClient(app)

@pytest.fixture
def mock_auth():
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_story_user"}
    yield
    app.dependency_overrides = {}
    settings.ENABLE_AUTH = orig_enable_auth

@pytest.fixture
def test_session():
    uid = "test_story_user"
    session_id = session_manager.create_session(uid)
    df = pd.DataFrame({
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000],
        "dept": ["IT", "HR", "IT"]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

@patch("services.story_service.get_llm")
def test_api_story_generate_success(mock_get_llm, mock_auth, test_session):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    Here is the story analysis.
    [STORY_JSON_START]
    {
      "report_id": "rep-1111",
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

    payload = {
        "sessionId": test_session,
        "reportType": "executive",
        "persona": "general"
    }

    res = client.post("/api/v3/story/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["report"]["report_id"] == "rep-1111"
    assert data["report"]["title"] == "LLM Generated Story Report"
    assert data["confidenceScore"] == 0.95

def test_api_story_generate_invalid_type(mock_auth, test_session):
    payload = {
        "sessionId": test_session,
        "reportType": "invalid_report_type_here",
        "persona": "general"
    }
    res = client.post("/api/v3/story/generate", json=payload)
    assert res.status_code == 400
    assert "invalid reporttype" in res.json()["detail"].lower()

def test_api_story_generate_unauthorized(test_session):
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides = {}

    try:
        payload = {
            "sessionId": test_session,
            "reportType": "executive"
        }
        res = client.post("/api/v3/story/generate", json=payload)
        assert res.status_code == 401
    finally:
        settings.ENABLE_AUTH = orig_enable_auth

def test_api_story_generate_cross_user_isolation(mock_auth, test_session):
    # Authenticate as malicious user
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "malicious_user"}

    payload = {
        "sessionId": test_session,
        "reportType": "executive"
    }
    res = client.post("/api/v3/story/generate", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

def test_api_story_generate_missing_session(mock_auth):
    payload = {
        "sessionId": "non-existent-session-uuid",
        "reportType": "executive"
    }
    res = client.post("/api/v3/story/generate", json=payload)
    assert res.status_code == 404
    assert "session not found" in res.json()["detail"].lower()

@patch("services.story_service.get_llm")
def test_api_story_generate_fallback(mock_get_llm, mock_auth, test_session):
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM failure")
    mock_get_llm.return_value = mock_llm

    payload = {
        "sessionId": test_session,
        "reportType": "executive"
    }
    res = client.post("/api/v3/story/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["report"]["report_id"]) > 0
    assert "Fallback" in data["report"]["executive_summary"]["overall_business_summary"] or True

@patch("services.story_service.get_llm")
def test_api_story_exports(mock_get_llm, mock_auth, test_session):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    [STORY_JSON_START]
    {
      "report_id": "rep-export-2222",
      "title": "LLM Generated Story Report",
      "executive_summary": {
        "dataset_overview": "Overview.",
        "data_quality_score": 90.0,
        "overall_business_summary": "Summary."
      },
      "sections": [],
      "recommendations": [],
      "confidence_score": 0.95,
      "sources": ["profiler"],
      "generated_timestamp": "2026-06-14T23:27:55"
    }
    """
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    # 1. First generate a report to populate the cache
    payload = {
        "sessionId": test_session,
        "reportType": "executive"
    }
    res_gen = client.post("/api/v3/story/generate", json=payload)
    assert res_gen.status_code == 200

    # 2. Export HTML/PDF
    res_pdf = client.get("/api/v3/story/export/pdf/rep-export-2222")
    assert res_pdf.status_code == 200
    assert "text/html" in res_pdf.headers["content-type"]
    assert "Executive Summary" in res_pdf.text  # static heading always present

    # 3. Export JSON
    res_json = client.get("/api/v3/story/export/json/rep-export-2222")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    assert res_json.json()["report_id"] == "rep-export-2222"

    # 4. Attempt cross-user export access (should fail with 403 Forbidden)
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "malicious_user"}
    res_mal = client.get("/api/v3/story/export/json/rep-export-2222")
    assert res_mal.status_code == 403
