import pytest
import os
import shutil
import pandas as pd
from fastapi.testclient import TestClient
from main import app
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager
from config.settings import settings

client = TestClient(app)

@pytest.fixture
def mock_auth():
    # Force ENABLE_AUTH to True for testing auth restrictions
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_user_execute"}
    yield
    app.dependency_overrides = {}
    settings.ENABLE_AUTH = orig_enable_auth

@pytest.fixture
def test_session():
    uid = "test_user_execute"
    session_id = session_manager.create_session(uid)
    # Row 0 and Row 1 are exact duplicates, Row 2 has a missing value
    df = pd.DataFrame({
        "A": [1, 1, 2],
        "B": [10.0, 10.0, None]
    })
    session_manager.save_dataframe(uid, session_id, df)
    yield session_id
    session_manager.cleanup_session(uid, session_id)

def test_execute_valid_session(mock_auth, test_session):
    payload = {
        "sessionId": test_session,
        "plan": {
            "actions": [
                {"action_id": "act-1", "recommendation": "remove_duplicates", "column_name": None},
                {"action_id": "act-2", "recommendation": "mean_imputation", "column_name": "B"}
            ]
        },
        "action_ids": ["act-1", "act-2"]
    }
    
    res = client.post("/api/v2/cleaning/execute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["sessionId"] == test_session
    assert data["metrics"]["rowsBefore"] == 3
    assert data["metrics"]["rowsAfter"] == 2
    assert len(data["applied_actions"]) == 2
    assert data["stats"]["duplicates_removed"] == 1
    assert data["stats"]["missing_values_filled"] == 1

def test_execute_unauthorized_access(test_session):
    # Enforce auth verification
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    app.dependency_overrides = {}
    
    try:
        payload = {
            "sessionId": test_session,
            "plan": {"actions": []}
        }
        res = client.post("/api/v2/cleaning/execute", json=payload)
        # Should be rejected since verify_firebase_token runs with ENABLE_AUTH=True and no bearer credentials
        assert res.status_code == 401
    finally:
        settings.ENABLE_AUTH = orig_enable_auth

def test_execute_wrong_user_session(test_session):
    # Authenticate as a different user
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "attacker_user"}
    
    payload = {
        "sessionId": test_session,
        "plan": {"actions": []}
    }
    res = client.post("/api/v2/cleaning/execute", json=payload)
    # Attacker user has no access to test_session (which belongs to test_user_execute), returns 404
    assert res.status_code == 404
    app.dependency_overrides = {}

def test_execute_missing_session(mock_auth):
    payload = {
        "sessionId": "nonexistent-session-id",
        "plan": {"actions": []}
    }
    res = client.post("/api/v2/cleaning/execute", json=payload)
    assert res.status_code == 404

def test_execute_backup_creation(mock_auth, test_session):
    uid = "test_user_execute"
    session_path = session_manager._session_path(uid, test_session)
    backup_file = session_path / "data_orig.parquet"
    
    # Assert backup doesn't exist yet
    assert not backup_file.exists()
    
    payload = {
        "sessionId": test_session,
        "plan": {
            "actions": [
                {"action_id": "act-1", "recommendation": "remove_duplicates", "column_name": None}
            ]
        }
    }
    
    res = client.post("/api/v2/cleaning/execute", json=payload)
    assert res.status_code == 200
    
    # Assert backup is created
    assert backup_file.exists()
    
    # Verify backup contains original data (3 rows)
    backup_df = pd.read_parquet(backup_file)
    assert len(backup_df) == 3
    
    # Active file has only cleaned data (2 rows)
    active_df = session_manager.load_dataframe(uid, test_session)
    assert len(active_df) == 2


def test_reset_happy_path(mock_auth, test_session):
    uid = "test_user_execute"
    # First, run an execution to create a backup
    payload = {
        "sessionId": test_session,
        "plan": {
            "actions": [
                {"action_id": "act-1", "recommendation": "remove_duplicates", "column_name": None}
            ]
        }
    }
    res = client.post("/api/v2/cleaning/execute", json=payload)
    assert res.status_code == 200
    
    # Assert active df has only 2 rows now
    active_df = session_manager.load_dataframe(uid, test_session)
    assert len(active_df) == 2
    
    # Call reset
    reset_res = client.post("/api/v2/cleaning/reset", json={"sessionId": test_session})
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True
    
    # Assert active df is restored to original 3 rows
    restored_df = session_manager.load_dataframe(uid, test_session)
    assert len(restored_df) == 3


def test_reset_no_backup(mock_auth, test_session):
    # Call reset directly on a session that has never been cleaned (no backup)
    res = client.post("/api/v2/cleaning/reset", json={"sessionId": test_session})
    assert res.status_code == 400
    assert "no original backup found" in res.json()["detail"].lower()


def test_reset_unauthorized(test_session):
    # Call reset as a different user
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "attacker_user"}
    try:
        res = client.post("/api/v2/cleaning/reset", json={"sessionId": test_session})
        # Should return 404 since the session belongs to test_user_execute and is not found for attacker_user
        assert res.status_code == 404
    finally:
        app.dependency_overrides = {}

