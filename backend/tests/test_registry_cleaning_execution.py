import sys
from unittest.mock import MagicMock, patch

# Pre-inject mock psycopg_pool module to avoid ModuleNotFoundError
mock_psycopg_pool = MagicMock()
sys.modules["psycopg_pool"] = mock_psycopg_pool

import pytest
import os
import re
import uuid
import tempfile
import shutil
import pandas as pd
from fastapi.testclient import TestClient

from main import app
from utils.auth import verify_firebase_token
from services.dataset_service import (
    get_dataset_service,
    InMemoryDatasetService,
    PostgresDatasetService,
    FirestoreDatasetService
)
from config.settings import settings

client = TestClient(app)

# ── 1. Mock Auth Fixture ──────────────────────────────────────────────────────

@pytest.fixture
def mock_auth():
    # Force ENABLE_AUTH to True for testing auth restrictions
    orig_enable_auth = settings.ENABLE_AUTH
    settings.ENABLE_AUTH = True
    
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_user_execute"}
    yield
    app.dependency_overrides = {}
    settings.ENABLE_AUTH = orig_enable_auth


# ── 2. Version Increment Logic Unit Tests ─────────────────────────────────────

def test_version_increment_logic():
    """Verify that file name formatting and version parsing works correctly."""
    def parse_new_filename(orig_name, current_version):
        base_name = orig_name.rsplit(".", 1)[0] if "." in orig_name else orig_name
        base_name = re.sub(r"_v\d+$", "", base_name)
        base_name = re.sub(r"^cleaned_", "", base_name)
        new_version = (current_version or 1) + 1
        return f"cleaned_{base_name}_v{new_version}.parquet", new_version

    assert parse_new_filename("sales.parquet", 1) == ("cleaned_sales_v2.parquet", 2)
    assert parse_new_filename("cleaned_sales_v2.parquet", 2) == ("cleaned_sales_v3.parquet", 3)
    assert parse_new_filename("raw_dataset", None) == ("cleaned_raw_dataset_v2.parquet", 2)
    assert parse_new_filename("my.file.name.parquet", 4) == ("cleaned_my.file.name_v5.parquet", 5)
    assert parse_new_filename("cleaned_data_v99.parquet", 99) == ("cleaned_data_v100.parquet", 100)


# ── 3. In-Memory Registry Endpoint Execution Tests ─────────────────────────────

def test_in_memory_registry_execution_happy_path(mock_auth):
    """Test standard registry-based cleaning using InMemoryDatasetService."""
    service = get_dataset_service()
    assert isinstance(service, InMemoryDatasetService)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save baseline parquet
        df = pd.DataFrame({
            "A": [1, 1, 2],
            "B": [10.0, 10.0, None]
        })
        orig_file = os.path.join(tmpdir, "original_sales.parquet")
        df.to_parquet(orig_file, index=False)
        
        # Register baseline
        dataset_id = "test-ds-v1"
        service.store[dataset_id] = {
            "dataset_id": dataset_id,
            "user_id": "test_user_execute",
            "dataset_name": "original_sales.parquet",
            "original_file_type": "parquet",
            "source": "upload",
            "upload_timestamp": "2026-06-14T12:00:00Z",
            "row_count": 3,
            "column_count": 2,
            "memory_usage": 0.1,
            "parquet_path": orig_file,
            "ml_readiness_score": 75,
            "dataset_version": 1,
            "status": "active"
        }
        
        payload = {
            "datasetId": dataset_id,
            "plan": {
                "actions": [
                    {"action_id": "act-1", "recommendation": "remove_duplicates", "column_name": None}
                ]
            }
        }
        
        res = client.post("/api/v2/cleaning/execute", json=payload)
        assert res.status_code == 200
        data = res.json()
        
        assert data["success"] is True
        new_ds_id = data["datasetId"]
        assert new_ds_id != dataset_id
        assert data["dataset_version"] == 2
        assert data["metrics"]["rowsBefore"] == 3
        assert data["metrics"]["rowsAfter"] == 2
        
        # Check metadata created
        new_meta = service.get_dataset(new_ds_id)
        assert new_meta is not None
        assert new_meta["parent_dataset_id"] == dataset_id
        assert new_meta["dataset_version"] == 2
        assert new_meta["dataset_name"] == "cleaned_original_sales_v2.parquet"
        assert os.path.exists(new_meta["parquet_path"])
        
        # Check original file remains unchanged
        assert os.path.exists(orig_file)
        orig_df = pd.read_parquet(orig_file)
        assert len(orig_df) == 3
        
        # Test consecutive versioning (v2 -> v3)
        payload_v3 = {
            "datasetId": new_ds_id,
            "plan": {
                "actions": []
            }
        }
        res_v3 = client.post("/api/v2/cleaning/execute", json=payload_v3)
        assert res_v3.status_code == 200
        data_v3 = res_v3.json()
        assert data_v3["dataset_version"] == 3
        
        new_ds_id_v3 = data_v3["datasetId"]
        new_meta_v3 = service.get_dataset(new_ds_id_v3)
        assert new_meta_v3["parent_dataset_id"] == new_ds_id
        assert new_meta_v3["dataset_name"] == "cleaned_original_sales_v3.parquet"


def test_registry_execution_ownership_validation(mock_auth):
    """Verify registry execution rejects requests for datasets owned by others."""
    service = get_dataset_service()
    assert isinstance(service, InMemoryDatasetService)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        df = pd.DataFrame({"A": [1, 2]})
        orig_file = os.path.join(tmpdir, "other_sales.parquet")
        df.to_parquet(orig_file, index=False)
        
        dataset_id = "test-other-ds"
        service.store[dataset_id] = {
            "dataset_id": dataset_id,
            "user_id": "other_owner", # Different owner
            "dataset_name": "other_sales.parquet",
            "original_file_type": "parquet",
            "source": "upload",
            "upload_timestamp": "2026-06-14T12:00:00Z",
            "row_count": 2,
            "column_count": 1,
            "memory_usage": 0.1,
            "parquet_path": orig_file,
            "ml_readiness_score": 75,
            "dataset_version": 1,
            "status": "active"
        }
        
        payload = {
            "datasetId": dataset_id,
            "plan": {"actions": []}
        }
        
        res = client.post("/api/v2/cleaning/execute", json=payload)
        # Should return 403 Forbidden
        assert res.status_code == 403
        assert "permission" in res.json()["detail"].lower()


def test_registry_execution_nonexistent_dataset(mock_auth):
    """Verify registry execution returns 404 for missing datasets."""
    payload = {
        "datasetId": "nonexistent-dataset-id",
        "plan": {"actions": []}
    }
    res = client.post("/api/v2/cleaning/execute", json=payload)
    assert res.status_code == 404


# ── 4. PostgreSQL Registry Service & Endpoint Mocks ────────────────────────────

def test_postgres_dataset_service_crud():
    """Verify PostgresDatasetService CRUD methods function correctly via mock connection pool."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    # Configure mock_psycopg_pool to return our mock_pool when ConnectionPool is initialized
    mock_psycopg_pool.ConnectionPool.return_value = mock_pool
    
    service = PostgresDatasetService("postgresql://user:pass@localhost:5432/db")
    
    # Verify schema table initialization
    assert mock_cur.execute.call_count >= 1
    mock_cur.reset_mock()
    
    # Test create_dataset
    test_data = {
        "dataset_id": "ds-pg",
        "user_id": "user-pg",
        "dataset_name": "pg.parquet",
        "original_file_type": "parquet",
        "source": "upload",
        "upload_timestamp": "2026-06-14T12:00:00Z",
        "row_count": 10,
        "column_count": 2,
        "memory_usage": 0.5,
        "parquet_path": "/path/pg.parquet",
        "ml_readiness_score": 85,
        "dataset_version": 1,
        "status": "active",
        "parent_dataset_id": "ds-parent"
    }
    service.create_dataset(test_data)
    mock_cur.execute.assert_called_once()
    insert_args = mock_cur.execute.call_args[0][1]
    assert insert_args == (
        "ds-pg", "user-pg", "pg.parquet", "parquet", "upload",
        "2026-06-14T12:00:00Z", 10, 2, 0.5,
        "/path/pg.parquet", 85, 1, "active", "ds-parent"
    )
    
    # Test get_dataset
    mock_cur.reset_mock()
    mock_cur.fetchone.return_value = (
        "ds-pg", "user-pg", "pg.parquet", "parquet", "upload",
        "2026-06-14T12:00:00Z", 10, 2, 0.5,
        "/path/pg.parquet", 85, 1, "active", "ds-parent"
    )
    mock_cur.description = [
        ("dataset_id",), ("user_id",), ("dataset_name",), ("original_file_type",), ("source",),
        ("upload_timestamp",), ("row_count",), ("column_count",), ("memory_usage",),
        ("parquet_path",), ("ml_readiness_score",), ("dataset_version",), ("status",),
        ("parent_dataset_id",)
    ]
    
    result = service.get_dataset("ds-pg")
    assert result is not None
    assert result["dataset_id"] == "ds-pg"
    assert result["parent_dataset_id"] == "ds-parent"
    mock_cur.execute.assert_called_with("SELECT * FROM datasets WHERE dataset_id = %s", ("ds-pg",))
    
    # Test update_dataset
    mock_cur.reset_mock()
    service.update_dataset("ds-pg", {"status": "inactive"})
    assert "UPDATE datasets SET" in mock_cur.execute.call_args[0][0]
    assert mock_cur.execute.call_args[0][1] == ("inactive", "ds-pg")
    
    # Test list_datasets
    mock_cur.reset_mock()
    mock_cur.fetchall.return_value = [
        (
            "ds-pg", "user-pg", "pg.parquet", "parquet", "upload",
            "2026-06-14T12:00:00Z", 10, 2, 0.5,
            "/path/pg.parquet", 85, 1, "active", "ds-parent"
        )
    ]
    list_res = service.list_datasets("user-pg")
    assert len(list_res) == 1
    assert list_res[0]["dataset_id"] == "ds-pg"
    mock_cur.execute.assert_called_with("SELECT * FROM datasets WHERE user_id = %s", ("user-pg",))
    
    # Test delete_dataset
    mock_cur.reset_mock()
    service.delete_dataset("ds-pg")
    mock_cur.execute.assert_called_with("DELETE FROM datasets WHERE dataset_id = %s", ("ds-pg",))


def test_postgres_api_execution(mock_auth):
    """Test endpoint executes successfully when PostgreSQL registry is configured."""
    mock_service = MagicMock(spec=PostgresDatasetService)
    
    original_meta = {
        "dataset_id": "ds-pg-v1",
        "user_id": "test_user_execute",
        "dataset_name": "postgres_data.parquet",
        "original_file_type": "parquet",
        "source": "upload",
        "upload_timestamp": "2026-06-14T12:00:00Z",
        "row_count": 3,
        "column_count": 2,
        "memory_usage": 0.1,
        "parquet_path": "", # Will be populated below
        "ml_readiness_score": 80,
        "dataset_version": 1,
        "status": "active",
        "parent_dataset_id": None
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        df = pd.DataFrame({"A": [1, 1, 2], "B": [10.0, 10.0, None]})
        orig_file = os.path.join(tmpdir, "postgres_data.parquet")
        df.to_parquet(orig_file, index=False)
        original_meta["parquet_path"] = orig_file
        
        mock_service.get_dataset.return_value = original_meta
        
        # Override get_dataset_service to return our mock postgres service
        app.dependency_overrides[get_dataset_service] = lambda: mock_service
        
        payload = {
            "datasetId": "ds-pg-v1",
            "plan": {"actions": []}
        }
        
        try:
            res = client.post("/api/v2/cleaning/execute", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["dataset_version"] == 2
            
            # Verify new Postgres metadata registered
            mock_service.create_dataset.assert_called_once()
            called_meta = mock_service.create_dataset.call_args[0][0]
            assert called_meta["dataset_version"] == 2
            assert called_meta["parent_dataset_id"] == "ds-pg-v1"
            assert "cleaned_postgres_data_v2.parquet" in called_meta["dataset_name"]
            
        finally:
            app.dependency_overrides.pop(get_dataset_service, None)


# ── 5. Firestore Registry Service & Endpoint Mocks ─────────────────────────────

def test_firestore_dataset_service_crud():
    """Verify FirestoreDatasetService CRUD methods function correctly via mock Firestore client."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_document = MagicMock()
    mock_doc_snapshot = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document
    mock_document.get.return_value = mock_doc_snapshot
    
    with patch("firebase_admin.firestore.client", return_value=mock_db):
        service = FirestoreDatasetService()
        
        # Test create_dataset
        test_data = {"dataset_id": "ds-fs", "user_id": "user-fs"}
        service.create_dataset(test_data)
        mock_db.collection.assert_called_with("datasets")
        mock_collection.document.assert_called_with("ds-fs")
        mock_document.set.assert_called_with(test_data)
        
        # Test get_dataset exists
        mock_document.reset_mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = test_data
        res = service.get_dataset("ds-fs")
        assert res == test_data
        mock_document.get.assert_called_once()
        
        # Test get_dataset not exists
        mock_doc_snapshot.exists = False
        res = service.get_dataset("ds-nonexistent")
        assert res is None
        
        # Test update_dataset
        service.update_dataset("ds-fs", {"status": "inactive"})
        mock_document.update.assert_called_with({"status": "inactive"})
        
        # Test delete_dataset
        service.delete_dataset("ds-fs")
        mock_document.delete.assert_called_once()
        
        # Test list_datasets
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = test_data
        mock_collection.where.return_value.stream.return_value = [mock_doc_snapshot]
        list_res = service.list_datasets("user-fs")
        assert len(list_res) == 1
        assert list_res[0]["user_id"] == "user-fs"


def test_firestore_api_execution(mock_auth):
    """Test endpoint executes successfully when Firestore registry is configured."""
    mock_service = MagicMock(spec=FirestoreDatasetService)
    
    original_meta = {
        "dataset_id": "ds-fs-v1",
        "user_id": "test_user_execute",
        "dataset_name": "firestore_data.parquet",
        "original_file_type": "parquet",
        "source": "upload",
        "upload_timestamp": "2026-06-14T12:00:00Z",
        "row_count": 3,
        "column_count": 2,
        "memory_usage": 0.1,
        "parquet_path": "", # Will be populated below
        "ml_readiness_score": 80,
        "dataset_version": 1,
        "status": "active",
        "parent_dataset_id": None
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        df = pd.DataFrame({"A": [1, 1, 2], "B": [10.0, 10.0, None]})
        orig_file = os.path.join(tmpdir, "firestore_data.parquet")
        df.to_parquet(orig_file, index=False)
        original_meta["parquet_path"] = orig_file
        
        mock_service.get_dataset.return_value = original_meta
        
        # Override get_dataset_service to return our mock firestore service
        app.dependency_overrides[get_dataset_service] = lambda: mock_service
        
        payload = {
            "datasetId": "ds-fs-v1",
            "plan": {"actions": []}
        }
        
        try:
            res = client.post("/api/v2/cleaning/execute", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["dataset_version"] == 2
            
            # Verify new Firestore document created/set
            mock_service.create_dataset.assert_called_once()
            called_meta = mock_service.create_dataset.call_args[0][0]
            assert called_meta["dataset_version"] == 2
            assert called_meta["parent_dataset_id"] == "ds-fs-v1"
            assert "cleaned_firestore_data_v2.parquet" in called_meta["dataset_name"]
            
        finally:
            app.dependency_overrides.pop(get_dataset_service, None)
