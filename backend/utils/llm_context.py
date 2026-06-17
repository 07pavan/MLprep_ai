from __future__ import annotations
from contextvars import ContextVar

# Thread-safe, async-safe context variables for active request overrides
current_llm_provider: ContextVar[str | None] = ContextVar("current_llm_provider", default=None)
current_llm_api_key: ContextVar[str | None] = ContextVar("current_llm_api_key", default=None)
current_llm_model: ContextVar[str | None] = ContextVar("current_llm_model", default=None)
