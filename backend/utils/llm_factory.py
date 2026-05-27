"""Centralized LLM factory — single source of truth for model instantiation.

Replaces the 4 duplicated _get_llm() functions across graph nodes.
Supports two tiers:
  - "fast"  → cheap model for intent classification, insights
  - "smart" → expensive model for code generation, visualization
"""
from __future__ import annotations
import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel

from config.settings import settings

logger = logging.getLogger(__name__)


def _create_groq(model: str, temperature: float, timeout: int) -> Optional[BaseChatModel]:
    """Try to create a Groq LLM client."""
    if not settings.GROQ_API_KEY:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            temperature=temperature,
            groq_api_key=settings.GROQ_API_KEY,
            timeout=timeout,
            max_retries=1,
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


_PROVIDER_MAP = {
    "groq": _create_groq,
    "google": _create_google,
}


def get_llm(tier: str = "smart") -> Optional[BaseChatModel]:
    """Get an LLM instance for the given tier.

    Tier routing:
      "fast"  → settings.FAST_MODEL  via settings.FAST_PROVIDER  (fallback to other provider)
      "smart" → settings.SMART_MODEL via settings.SMART_PROVIDER (fallback to other provider)

    Returns None if all providers fail.
    """
    if tier == "fast":
        model = settings.FAST_MODEL
        primary_provider = settings.FAST_PROVIDER
        temperature = 0.0  # deterministic for classification
    else:
        model = settings.SMART_MODEL
        primary_provider = settings.SMART_PROVIDER
        temperature = settings.TEMPERATURE

    timeout = settings.LLM_TIMEOUT

    # Try primary provider
    primary_fn = _PROVIDER_MAP.get(primary_provider)
    if primary_fn:
        llm = primary_fn(model, temperature, timeout)
        if llm is not None:
            return llm

    # Fallback to the other provider with the same model name
    # (may fail if model isn't available on that provider, which is fine)
    fallback_providers = [p for p in _PROVIDER_MAP if p != primary_provider]
    for fb_provider in fallback_providers:
        fb_fn = _PROVIDER_MAP[fb_provider]
        # Use the backup model for cross-provider fallback
        fb_model = settings.FAST_MODEL if fb_provider == "google" else settings.SMART_MODEL
        llm = fb_fn(fb_model, temperature, timeout)
        if llm is not None:
            logger.info("LLM tier='%s': fell back to %s/%s", tier, fb_provider, fb_model)
            return llm

    logger.error("LLM tier='%s': ALL providers failed. Check API keys.", tier)
    return None
