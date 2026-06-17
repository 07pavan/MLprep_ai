from __future__ import annotations
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from utils.llm_context import current_llm_provider, current_llm_api_key, current_llm_model

class LLMContextMiddleware(BaseHTTPMiddleware):
    """Middleware to intercept custom LLM headers and configure request context."""
    
    async def dispatch(self, request: Request, call_next):
        # 1. Read custom client headers (case-insensitive)
        provider = request.headers.get("x-llm-provider")
        api_key = request.headers.get("x-llm-api-key")
        model = request.headers.get("x-llm-model")

        # 2. Set ContextVars and obtain tokens to reset context after the request completes
        t_provider = current_llm_provider.set(provider) if provider else None
        t_api_key = current_llm_api_key.set(api_key) if api_key else None
        t_model = current_llm_model.set(model) if model else None

        try:
            response = await call_next(request)
            return response
        finally:
            # 3. Reset the context variables to prevent credential bleeding in concurrent tasks
            if t_provider:
                current_llm_provider.reset(t_provider)
            if t_api_key:
                current_llm_api_key.reset(t_api_key)
            if t_model:
                current_llm_model.reset(t_model)
