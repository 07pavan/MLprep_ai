import pytest
import os
import sys
import base64
import logging
import asyncio
import tempfile
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock psycopg_pool before importing dataset_service
mock_psycopg_pool = MagicMock()
sys.modules["psycopg_pool"] = mock_psycopg_pool

from config.settings import settings, BACKEND_DIR

# 1. Postgres Schema Preservation Test
def test_postgres_schema_preservation():
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    # Retrieve the psycopg_pool mock that is actually active in sys.modules to avoid collision
    active_psycopg_pool = sys.modules.get("psycopg_pool")
    if active_psycopg_pool is None:
        active_psycopg_pool = MagicMock()
        sys.modules["psycopg_pool"] = active_psycopg_pool
    else:
        active_psycopg_pool.reset_mock()
        
    active_psycopg_pool.ConnectionPool.return_value = mock_pool
    
    from services.dataset_service import PostgresDatasetService
    
    # Instantiate service, which calls init_db()
    service = PostgresDatasetService("postgresql://test:test@localhost:5432/test")
    
    # Verify ConnectionPool was called
    active_psycopg_pool.ConnectionPool.assert_called_once()
    
    # Verify init_db executed queries
    assert mock_cur.execute.called
    
    # Verify absolutely no DROP TABLE statement was executed
    has_create_table = False
    for call in mock_cur.execute.call_args_list:
        query = call[0][0]
        assert "DROP TABLE" not in query
        if "CREATE TABLE IF NOT EXISTS datasets" in query:
            has_create_table = True
    assert has_create_table


# 2. Ephemeral Storage Warning Test
@patch("main.logger")
@patch("firebase_admin.initialize_app")
@patch("firebase_admin.credentials.Certificate")
def test_ephemeral_storage_warning(mock_certificate, mock_initialize, mock_logger):
    import main
    
    # Scenario A: Production auth enabled, but STORAGE_DIR is default local/ephemeral -> Warning is logged
    with patch.object(settings, "ENABLE_AUTH", True), \
         patch.object(settings, "STORAGE_DIR", str(BACKEND_DIR / "storage")):
        asyncio.run(main.on_startup())
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list if call[0]]
        assert any("default ephemeral storage" in w for w in warning_calls)

    mock_logger.reset_mock()

    # Scenario B: Production auth enabled, and STORAGE_DIR is set to custom persistent path -> No Warning
    with patch.object(settings, "ENABLE_AUTH", True), \
         patch.object(settings, "STORAGE_DIR", "/app/storage"):
        asyncio.run(main.on_startup())
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list if call[0]]
        assert not any("default ephemeral storage" in w for w in warning_calls)


# 3. Firebase Credentials Decoding Test
def test_firebase_credentials_decoding():
    # Use a real temp directory for STORAGE_DIR to avoid complex mocking of Path
    with tempfile.TemporaryDirectory() as temp_dir:
        dummy_json = '{"type": "service_account"}'
        encoded_json = base64.b64encode(dummy_json.encode("utf-8")).decode("utf-8")
        
        # Patch settings attributes on settings instance directly
        original_json = settings.FIREBASE_SERVICE_ACCOUNT_JSON
        original_storage = settings.STORAGE_DIR
        original_creds = settings.GOOGLE_APPLICATION_CREDENTIALS
        original_env_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        
        settings.FIREBASE_SERVICE_ACCOUNT_JSON = encoded_json
        settings.STORAGE_DIR = temp_dir
        settings.GOOGLE_APPLICATION_CREDENTIALS = "/env/pre-existing-credentials-path"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/env/pre-existing-credentials-path"
        
        try:
            # Reload main module to run the module-level credentials decode block
            import main
            importlib.reload(main)
            
            # Verify the file was written
            expected_file = Path(temp_dir) / "firebase-key.json"
            assert expected_file.exists()
            assert expected_file.read_text() == dummy_json
            
            # Verify internal credentials variable is overridden to point to decoded JSON file
            assert settings.GOOGLE_APPLICATION_CREDENTIALS == str(expected_file.resolve())
            
            # Verify environment variable is updated to point to the resolved decoded file
            assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(expected_file.resolve())
            
        finally:
            # Restore settings
            settings.FIREBASE_SERVICE_ACCOUNT_JSON = original_json
            settings.STORAGE_DIR = original_storage
            settings.GOOGLE_APPLICATION_CREDENTIALS = original_creds
            if original_env_creds is not None:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = original_env_creds
            else:
                os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


# 4. Firestore Collection Group Index Missing Error Handling Test
@patch("firebase_admin.firestore.client")
def test_firestore_index_missing_error_handling(mock_firestore_client):
    # Set up mock DB client and mock stream that throws a FailedPrecondition exception
    mock_db = MagicMock()
    mock_firestore_client.return_value = mock_db
    
    mock_query = MagicMock()
    mock_db.collection_group.return_value = mock_query
    mock_query.where.return_value = mock_query
    
    # Mock stream to raise an exception containing FailedPrecondition
    mock_query.stream.side_effect = Exception("FailedPrecondition: The query requires a collection group index. Create it here: https://console.firebase.google.com/...")
    
    from services.chat_service import FirestoreChatService
    
    service = FirestoreChatService()
    
    # Verify that calling get_thread raises a clean RuntimeError and hides the internal exception details
    with pytest.raises(RuntimeError) as exc_info:
        service.get_thread("thread_123", "user_123")
    
    assert "Database configuration error: Required index is missing" in str(exc_info.value)


# 5. JSON Logging Formatter Test
def test_json_formatter_logs_valid_json():
    from utils.logging_config import JsonFormatter
    import json
    
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_service",
        level=logging.INFO,
        pathname="test_path.py",
        lineno=10,
        msg="Test logging message: %s",
        args=("hello",),
        exc_info=None
    )
    
    # Format and verify output
    formatted_str = formatter.format(record)
    log_json = json.loads(formatted_str)
    
    assert log_json["level"] == "INFO"
    assert log_json["service"] == "test_service"
    assert log_json["message"] == "Test logging message: hello"
    assert "timestamp" in log_json


# 6. Sentry DSN Configuration & Initialization Test
@patch("sentry_sdk.init")
def test_sentry_initialization(mock_sentry_init):
    # Set SENTRY_DSN on settings singleton directly
    original_dsn = settings.SENTRY_DSN
    settings.SENTRY_DSN = "https://public@sentry.io/12345"
    
    try:
        import main
        importlib.reload(main)
        
        # Verify sentry_sdk.init was called
        mock_sentry_init.assert_called_once()
        kwargs = mock_sentry_init.call_args[1]
        
        # Verify safety configurations are set correctly
        assert kwargs["dsn"] == "https://public@sentry.io/12345"
        assert kwargs["send_default_pii"] is False
        assert "before_send" in kwargs
        
        # Verify before_send sanitizes auth headers
        before_send_func = kwargs["before_send"]
        dummy_event = {
            "request": {
                "headers": {
                    "authorization": "Bearer super-secret-firebase-token",
                    "cookie": "session-cookie-secret",
                    "host": "localhost:8000"
                }
            }
        }
        sanitized_event = before_send_func(dummy_event, None)
        headers = sanitized_event["request"]["headers"]
        assert headers["authorization"] == "[REDACTED]"
        assert headers["cookie"] == "[REDACTED]"
        assert headers["host"] == "localhost:8000"  # Unaffected
        
    finally:
        settings.SENTRY_DSN = original_dsn


# 7. Request Context Middleware Test
def test_request_logging_middleware():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    
    # We will instantiate a mock FastAPI app with our middleware to test it cleanly
    app = FastAPI()
    
    # Inject log_requests middleware from main.py namespace
    import main
    app.middleware("http")(main.log_requests)
    
    @app.get("/test-endpoint")
    async def dummy_endpoint():
        return {"status": "ok"}
        
    # Execute a client request and verify request ID header is returned
    client = TestClient(app)
    
    with patch("main.logger") as mock_logger:
        response = client.get("/test-endpoint")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 10
        
        # Verify logger.info was called with request id and metadata extra
        mock_logger.info.assert_called_once()
        logger_call_kwargs = mock_logger.info.call_args[1]
        assert "extra" in logger_call_kwargs
        extra = logger_call_kwargs["extra"]
        assert extra["request_id"] == request_id
        assert extra["method"] == "GET"
        assert extra["path"] == "/test-endpoint"
        assert extra["status_code"] == 200


