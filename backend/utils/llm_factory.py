"""Centralized LLM factory — single source of truth for model instantiation.

Replaces standard LLM clients with dynamic, custom-configured keys and providers
extracted from the request context, supporting both Groq and OpenRouter.
"""
from __future__ import annotations
import httpx
import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel

from config.settings import settings
from utils.llm_context import current_llm_provider, current_llm_api_key, current_llm_model
from utils.rate_limit_tracker import update_rate_limits

logger = logging.getLogger(__name__)


def intercept_rate_limits(response: httpx.Response):
    """Response hook to intercept Groq rate limit headers and update tracker."""
    headers = response.headers
    rem_req = headers.get("x-ratelimit-remaining-requests")
    reset_req = headers.get("x-ratelimit-reset-requests")
    rem_tokens = headers.get("x-ratelimit-remaining-tokens")
    reset_tokens = headers.get("x-ratelimit-reset-tokens")
    
    if rem_req is not None:
        req_auth = response.request.headers.get("authorization") or response.request.headers.get("Authorization")
        api_key = None
        if req_auth:
            if req_auth.lower().startswith("bearer "):
                api_key = req_auth[7:]
            else:
                api_key = req_auth
        
        try:
            update_rate_limits(
                api_key,
                int(rem_req) if rem_req.isdigit() else None,
                reset_req,
                int(rem_tokens) if rem_tokens and rem_tokens.isdigit() else None,
                reset_tokens
            )
        except Exception:
            pass


# Configured sync and async HTTP clients with response interceptors
_async_client = httpx.AsyncClient(event_hooks={"response": [intercept_rate_limits]})
_sync_client = httpx.Client(event_hooks={"response": [intercept_rate_limits]})


def _create_groq(model: str, temperature: float, timeout: int, api_key: str | None = None) -> Optional[BaseChatModel]:
    """Try to create a Groq LLM client."""
    key = api_key or settings.GROQ_API_KEY
    if not key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            temperature=temperature,
            groq_api_key=key,
            timeout=timeout,
            max_retries=1,
            async_client=_async_client,
        )
    except Exception as exc:
        logger.warning("Failed to create Groq client (%s): %s", model, exc)
        return None


def _create_google(model: str, temperature: float, timeout: int) -> Optional[BaseChatModel]:
    """Try to create a Google Generative AI client."""
    if not settings.GOOGLE_API_KEY:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=settings.GOOGLE_API_KEY,
            timeout=timeout,
            max_retries=1,
        )
    except Exception as exc:
        logger.warning("Failed to create Google client (%s): %s", model, exc)
        return None


def _create_openrouter(model: str, temperature: float, timeout: int, api_key: str) -> Optional[BaseChatModel]:
    """Create a ChatOpenAI client configured for OpenRouter API endpoints."""
    try:
        from langchain_openai import ChatOpenAI
        target_model = model or "meta-llama/llama-3.1-8b-instruct"
        return ChatOpenAI(
            model=target_model,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://datacopilote-ai.netlify.app",
                "X-Title": "DataCopilote v2.1"
            },
            timeout=timeout,
            max_retries=1,
            http_client=_sync_client,
            http_async_client=_async_client,
        )
    except Exception as exc:
        logger.warning("Failed to create OpenRouter client (%s): %s", model, exc)
        return None


_PROVIDER_MAP = {
    "groq": _create_groq,
    "google": _create_google,
}


def get_llm(tier: str = "smart") -> Optional[BaseChatModel]:
    """Get an LLM instance for the given tier, supporting context-level overrides.

    Tier routing:
      "fast"  → settings.FAST_MODEL  via settings.FAST_PROVIDER
      "smart" → settings.SMART_MODEL via settings.SMART_PROVIDER
    """
    # 1. Resolve context variables for runtime overrides (custom API keys/providers)
    custom_provider = current_llm_provider.get()
    custom_key = current_llm_api_key.get()
    custom_model = current_llm_model.get()

    if tier == "fast":
        default_model = settings.FAST_MODEL
        primary_provider = settings.FAST_PROVIDER
        temperature = 0.0  # deterministic for classification
    else:
        default_model = settings.SMART_MODEL
        primary_provider = settings.SMART_PROVIDER
        temperature = settings.TEMPERATURE

    timeout = settings.LLM_TIMEOUT

    # 2. If a custom user API key is provided in the request context, bypass system defaults
    if custom_key:
        provider_type = (custom_provider or "groq").lower()
        if "openrouter" in provider_type:
            # For OpenRouter, select default models if user didn't specify one
            fallback_model = "meta-llama/llama-3.1-8b-instruct" if tier == "fast" else "meta-llama/llama-3.3-70b-instruct"
            model_name = custom_model or fallback_model
            logger.debug("Creating dynamic OpenRouter LLM: model=%s", model_name)
            return _create_openrouter(model_name, temperature, timeout, custom_key)
        else:
            # Default custom provider is Groq
            fallback_model = settings.FAST_MODEL if tier == "fast" else settings.SMART_MODEL
            model_name = custom_model or fallback_model
            logger.debug("Creating dynamic Groq LLM: model=%s", model_name)
            return _create_groq(model_name, temperature, timeout, custom_key)

    # 3. Fallback to system default keys and config.py settings
    primary_fn = _PROVIDER_MAP.get(primary_provider)
    if primary_fn:
        llm = primary_fn(default_model, temperature, timeout)
        if llm is not None:
            return llm

    # Fallback to the other default provider if configured
    fallback_providers = [p for p in _PROVIDER_MAP if p != primary_provider]
    for fb_provider in fallback_providers:
        fb_fn = _PROVIDER_MAP[fb_provider]
        fb_model = settings.FAST_MODEL if fb_provider == "google" else settings.SMART_MODEL
        llm = fb_fn(fb_model, temperature, timeout)
        if llm is not None:
            logger.info("LLM tier='%s': fell back to default %s/%s", tier, fb_provider, fb_model)
            return llm

    logger.error("LLM tier='%s': ALL providers failed. Check system API keys.", tier)
    return None
