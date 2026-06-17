"""
Unit and integration tests for the dataset URL import API router (routers/imports.py).
Verifies request payload validation, exception translation to HTTP status codes,
and end-to-end ingestion pipeline invocation.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
import pandas as pd

from main import app
from utils.auth import verify_firebase_token
from services.dataset_service import get_dataset_service
from services.dataset_source_service import DatasetLoadException
from services.http_dataset_downloader import DownloadException, DownloadSizeLimitExceeded
from utils.url_validator import UnsafeURLException


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_import_endpoint_requires_auth(client):
    """Verify that unauthenticated requests to the import endpoint are rejected."""
    # Temporarily remove verify_firebase_token override to test protection
    if verify_firebase_token in app.dependency_overrides:
        original = app.dependency_overrides.pop(verify_firebase_token)
    else:
        original = None

    try:
        # Request without Authorization header should be rejected
        response = client.post("/api/datasets/import", json={"url": "https://example.com/data.csv"})
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
    finally:
        if original:
            app.dependency_overrides[verify_firebase_token] = original


def test_successful_import_workflow(client):
    """Verify that a valid URL import executes the download, parse, and ingestion pipeline successfully."""
    url = "https://example.com/sub/employee_list.csv"
    mock_df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    
    # Configure mock authentication
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_user_123"}
    
    # Mock load_remote_dataset to bypass actual downloads and parsing
    with patch("routers.imports.load_remote_dataset", return_value=mock_df) as mock_load:
         response = client.post("/api/datasets/import", json={"url": url})
         
         # Verify endpoint returned 201 Created
         assert response.status_code == status.HTTP_201_CREATED
         data = response.json()
         
         # Verify returned response schema match
         assert "sessionId" in data
         assert "datasetId" in data
         assert data["filename"] == "employee_list.csv"
         assert data["format"] == "csv"
         assert data["shape"] == {"rows": 2, "cols": 2}
         assert len(data["columns"]) == 2
         
         # Verify download parser was called with URL
         mock_load.assert_called_once_with(url)
         
         # Verify the dataset was registered in metadata registry
         registry = get_dataset_service()
         dataset = registry.get_dataset(data["datasetId"])
         assert dataset is not None
         assert dataset["user_id"] == "test_user_123"
         assert dataset["dataset_name"] == "employee_list.csv"
         assert dataset["source"] == "cloud"


def test_import_unsafe_url_returns_400(client):
    """Verify that SSRF URLs are rejected with a 400 Bad Request."""
    url = "http://localhost/metadata"
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_user_123"}
    
    with patch("routers.imports.load_remote_dataset", side_effect=UnsafeURLException("SSRF URL blocked")):
        response = client.post("/api/datasets/import", json={"url": url})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "URL validation failed" in response.json()["detail"]


def test_import_exceeded_size_returns_413(client):
    """Verify that remote datasets exceeding size limits return a 413 Payload Too Large."""
    url = "https://example.com/gigantic.parquet"
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_user_123"}
    
    with patch("routers.imports.load_remote_dataset", side_effect=DownloadSizeLimitExceeded("Too large")):
        response = client.post("/api/datasets/import", json={"url": url})
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def test_import_parse_error_returns_422(client):
    """Verify that parsing/load failures return a 422 Unprocessable Entity."""
    url = "https://example.com/corrupted.json"
    app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "test_user_123"}
    
    with patch("routers.imports.load_remote_dataset", side_effect=DatasetLoadException("Malformed JSON")):
        response = client.post("/api/datasets/import", json={"url": url})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Failed to parse and load dataset" in response.json()["detail"]
