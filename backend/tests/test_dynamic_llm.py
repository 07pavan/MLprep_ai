import pytest
import asyncio
from unittest.mock import MagicMock, patch
from fastapi import Request
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from main import app
from config.settings import settings
from utils.llm_context import current_llm_provider, current_llm_api_key, current_llm_model
from utils.llm_middleware import LLMContextMiddleware
from utils.llm_factory import get_llm
from utils.rate_limit_tracker import get_rate_limits, update_rate_limits, query_rate_limits

client = TestClient(app)

@pytest.mark.anyio
async def test_context_variables_isolation():
    """Test that context variables do not leak across asynchronous tasks."""
    async def task_one():
        current_llm_provider.set("groq")
        current_llm_api_key.set("key_one")
        current_llm_model.set("model_one")
        await asyncio.sleep(0.1)
        assert current_llm_provider.get() == "groq"
        assert current_llm_api_key.get() == "key_one"
        assert current_llm_model.get() == "model_one"

    async def task_two():
        await asyncio.sleep(0.05)
        # Verify that task_one's values haven't bled into this context
        assert current_llm_provider.get() is None
        assert current_llm_api_key.get() is None
        assert current_llm_model.get() is None
        current_llm_provider.set("openrouter")
        current_llm_api_key.set("key_two")
        current_llm_model.set("model_two")
        await asyncio.sleep(0.1)
        assert current_llm_provider.get() == "openrouter"
        assert current_llm_api_key.get() == "key_two"
        assert current_llm_model.get() == "model_two"

    await asyncio.gather(task_one(), task_two())


@pytest.mark.anyio
async def test_middleware_extraction_and_reset():
    """Test that the middleware correctly sets ContextVars and resets them post-request."""
    middleware = LLMContextMiddleware(app=MagicMock())

    req = MagicMock(spec=Request)
    req.headers = Headers({
        "x-llm-provider": "openrouter",
        "x-llm-api-key": "test_api_key",
        "x-llm-model": "test_model"
    })

    async def mock_call_next(request):
        # Within the request lifecycle, ContextVars must be set
        assert current_llm_provider.get() == "openrouter"
        assert current_llm_api_key.get() == "test_api_key"
        assert current_llm_model.get() == "test_model"
        return "response"

    # Initially None
    assert current_llm_provider.get() is None
    assert current_llm_api_key.get() is None
    assert current_llm_model.get() is None

    res = await middleware.dispatch(req, mock_call_next)
    assert res == "response"

    # Reset back to None after middleware completes
    assert current_llm_provider.get() is None
    assert current_llm_api_key.get() is None
    assert current_llm_model.get() is None


@patch("utils.llm_factory._create_groq")
@patch("utils.llm_factory._create_openrouter")
def test_llm_factory_routing_with_custom_context(mock_create_openrouter, mock_create_groq):
    """Test get_llm routing based on active context overrides."""
    # 1. Groq dynamic route
    t_provider = current_llm_provider.set("groq")
    t_api_key = current_llm_api_key.set("user_groq_key")
    t_model = current_llm_model.set("llama3-8b")
    try:
        get_llm(tier="fast")
        mock_create_groq.assert_called_with("llama3-8b", 0.0, settings.LLM_TIMEOUT, "user_groq_key")
    finally:
        current_llm_provider.reset(t_provider)
        current_llm_api_key.reset(t_api_key)
        current_llm_model.reset(t_model)

    # 2. OpenRouter dynamic route
    t_provider = current_llm_provider.set("openrouter")
    t_api_key = current_llm_api_key.set("user_openrouter_key")
    t_model = current_llm_model.set("google/gemini-2.0")
    try:
        get_llm(tier="smart")
        mock_create_openrouter.assert_called_with("google/gemini-2.0", settings.TEMPERATURE, settings.LLM_TIMEOUT, "user_openrouter_key")
    finally:
        current_llm_provider.reset(t_provider)
        current_llm_api_key.reset(t_api_key)
        current_llm_model.reset(t_model)


def test_rate_limits_tracker_api():
    """Test rate limit tracker cache storage and the query endpoint."""
    test_key = "some_user_private_key"
    update_rate_limits(
        api_key=test_key,
        remaining_req=42,
        reset_req="15s",
        remaining_tokens=999,
        reset_tokens="30s"
    )

    # Direct query retrieval
    limits = get_rate_limits(test_key)
    assert limits["remaining_requests"] == 42
    assert limits["reset_requests"] == "15s"
    assert limits["remaining_tokens"] == 999
    assert limits["reset_tokens"] == "30s"

    # API Endpoint retrieval
    headers = {"X-LLM-API-Key": test_key}
    response = client.get("/api/v3/llm/rate-limits", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["remaining_requests"] == 42
    assert data["reset_requests"] == "15s"
    assert data["remaining_tokens"] == 999
    assert data["reset_tokens"] == "30s"
