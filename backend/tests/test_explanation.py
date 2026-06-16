import pytest
import os
import pandas as pd
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from schemas.explanation import ExplanationRequest, ExplanationResponse
from services.explanation_service import (
    ExplanationService,
    get_explanation_service,
    sanitize_pii_columns
)
from utils.session_manager import session_manager
from services.dataset_service import get_dataset_service

@pytest.fixture
def test_session():
    uid = "test_explanation_user"
    session_id = session_manager.create_session(uid)
    # Include both normal columns and PII-like columns
    df = pd.DataFrame({
        "customer_id": [1, 2, 3],
        "customer_email": ["a@example.com", "b@example.com", "c@example.com"],
        "phone_number": ["123", "456", "789"],
        "ssn": ["000-00-0000", "000-00-0001", "000-00-0002"],
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

def test_explanation_request_validation():
    # Valid request
    req = ExplanationRequest(
        sessionId="session_abc",
        aspect="profiling",
        persona="general"
    )
    assert req.sessionId == "session_abc"
    assert req.aspect == "profiling"
    assert req.persona == "general"

    # Default persona
    req_default = ExplanationRequest(
        sessionId="session_abc",
        aspect="general"
    )
    assert req_default.persona == "general"


def test_pii_sanitization():
    cols = ["customer_id", "customer_email", "phone_number", "ssn", "age", "salary"]
    sanitized, mapping = sanitize_pii_columns(cols)
    
    # Check that PII fields are mapped to anonymized tags
    assert "customer_email" in mapping
    assert "phone_number" in mapping
    assert "ssn" in mapping
    assert "customer_id" not in mapping
    assert "age" not in mapping
    assert "salary" not in mapping
    
    assert mapping["customer_email"] == "[ANONYMIZED_PII_1]"
    assert mapping["phone_number"] == "[ANONYMIZED_PII_2]"
    assert mapping["ssn"] == "[ANONYMIZED_PII_3]"
    
    assert sanitized == ["customer_id", "[ANONYMIZED_PII_1]", "[ANONYMIZED_PII_2]", "[ANONYMIZED_PII_3]", "age", "salary"]


def test_prompt_generation_does_not_contain_raw_rows():
    service = ExplanationService()
    metrics = {
        "profiling": {
            "rows": 100,
            "columns": 5,
            "column_names": ["id", "val"],
            "dtypes": {"id": "int64", "val": "float64"},
            "numerical_stats": {"val": {"mean": 10.5}}
        }
    }
    prompt = service._build_prompt("profiling", metrics, "general")
    
    assert "You are a Senior Data Analyst" in prompt
    assert "Row count: 100" in prompt
    assert "Column count: 5" in prompt
    # Verify no raw rows/values from dataset are present or requested
    assert "val: 10.5" in prompt or "mean" in prompt


@patch("services.explanation_service.get_llm")
def test_llm_success_path(mock_get_llm, test_session):
    uid = "test_explanation_user"
    mock_llm = MagicMock()
    # Mock LLM to return formatted summary and insights separated by the tag
    mock_response = MagicMock()
    mock_response.content = "This is a great dataset. [INSIGHTS_START]\n* Insight 1\n* Insight 2"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = get_explanation_service()
    res_data = service.get_explanation(uid, test_session, "profiling", "general")
    
    assert res_data["success"] is True
    assert res_data["summary"] == "This is a great dataset."
    assert "Insight 1" in res_data["insights"]
    assert "Insight 2" in res_data["insights"]
    assert res_data["confidence"] == 0.90
    assert "profiler" in res_data["sources"]
    assert "profiling" in res_data["raw_metrics"]


@patch("services.explanation_service.get_llm")
def test_llm_failure_fallback(mock_get_llm, test_session):
    uid = "test_explanation_user"
    # LLM raises an error during invocation to trigger the fallback
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM connection timed out")
    mock_get_llm.return_value = mock_llm

    service = ExplanationService()
    res_data = service.get_explanation(uid, test_session, "profiling", "general")
    
    # Fallback should succeed and report success=True with fallback metrics
    assert res_data["success"] is True
    assert "contains 3 rows" in res_data["summary"]
    assert any("Features include:" in ins for ins in res_data["insights"])
    assert res_data["confidence"] == 0.70
    assert "profiler" in res_data["sources"]
    assert "profiling" in res_data["raw_metrics"]


@patch("services.explanation_service.get_llm")
def test_aspect_selections(mock_get_llm, test_session):
    uid = "test_explanation_user"
    # Force fallback path to test deterministic aspect metrics easily
    mock_get_llm.return_value = None
    service = ExplanationService()

    # Test Profiling aspect
    res_prof = service.get_explanation(uid, test_session, "profiling")
    assert "profiling" in res_prof["raw_metrics"]
    assert "quality" not in res_prof["raw_metrics"]
    assert "ml_readiness" not in res_prof["raw_metrics"]
    assert "profiler" in res_prof["sources"]

    # Test Quality aspect
    res_qual = service.get_explanation(uid, test_session, "quality")
    assert "quality" in res_qual["raw_metrics"]
    assert "profiling" not in res_qual["raw_metrics"]
    assert "ml_readiness" not in res_qual["raw_metrics"]
    assert "quality" in res_qual["sources"]

    # Test ML Readiness aspect
    res_ml = service.get_explanation(uid, test_session, "ml_readiness")
    assert "ml_readiness" in res_ml["raw_metrics"]
    assert "profiling" not in res_ml["raw_metrics"]
    assert "quality" not in res_ml["raw_metrics"]
    assert "ml_readiness" in res_ml["sources"]

    # Test Cleaning History aspect (with mocked dataset service)
    with patch("services.explanation_service.get_dataset_service") as mock_get_ds_service:
        mock_ds_service = MagicMock()
        # Mock list_datasets to return registry metadata
        mock_ds_service.list_datasets.return_value = [
            {
                "dataset_id": "ds_1",
                "dataset_name": "original.csv",
                "dataset_version": 1,
                "row_count": 5,
                "column_count": 6,
                "upload_timestamp": "2026-06-14T20:00:00",
                "parent_dataset_id": None,
                "parquet_path": session_manager.get_data_path(uid, test_session)
            }
        ]
        mock_get_ds_service.return_value = mock_ds_service
        
        res_hist = service.get_explanation(uid, test_session, "cleaning_history")
        assert "cleaning_history" in res_hist["raw_metrics"]
        assert len(res_hist["raw_metrics"]["cleaning_history"]) == 1
        assert res_hist["raw_metrics"]["cleaning_history"][0]["dataset_name"] == "original.csv"
        assert "dataset_service" in res_hist["sources"]


@patch("services.explanation_service.get_llm")
def test_invalid_aspect_graceful_fallback(mock_get_llm, test_session):
    uid = "test_explanation_user"
    mock_get_llm.return_value = None
    service = ExplanationService()

    # Invalid aspect should fall back to general-style response gracefully
    res = service.get_explanation(uid, test_session, "invalid_aspect")
    assert res["success"] is True
    assert "General overview of dataset" in res["summary"]
    assert len(res["insights"]) > 0
    assert res["confidence"] == 0.70


def test_non_existent_session_raises_error():
    service = ExplanationService()
    # Querying a non-existent session should raise FileNotFoundError or similar when load_dataframe fails
    with pytest.raises(Exception):
        service.get_explanation("test_explanation_user", "non-existent-session-id", "profiling")


@patch("services.explanation_service.get_llm")
def test_cache_layer_reuse(mock_get_llm, test_session):
    uid = "test_explanation_user"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Cached summary [INSIGHTS_START]\n* Cached insight"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    service = ExplanationService()
    
    # First call: should invoke LLM
    res_1 = service.get_explanation(uid, test_session, "profiling")
    assert mock_llm.invoke.call_count == 1
    
    # Second call: should hit cache and not invoke LLM again
    res_2 = service.get_explanation(uid, test_session, "profiling")
    assert mock_llm.invoke.call_count == 1
    assert res_2["summary"] == res_1["summary"]
    assert res_2["insights"] == res_1["insights"]
