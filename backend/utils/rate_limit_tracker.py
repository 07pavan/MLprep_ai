from __future__ import annotations
import logging
import hashlib
from threading import Lock
from typing import Dict, Any, Optional
from fastapi import APIRouter, Header

logger = logging.getLogger(__name__)

# Thread-safe global cache for rate limits, keyed by MD5 hash of API key
_rate_limits_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = Lock()

def get_api_key_hash(api_key: str | None) -> str:
    """Generate MD5 hash of API key for safe cache indexing."""
    if not api_key:
        return "default"
    return hashlib.md5(api_key.encode("utf-8")).hexdigest()

def update_rate_limits(
    api_key: str | None,
    remaining_req: int | None,
    reset_req: str | None,
    remaining_tokens: int | None = None,
    reset_tokens: str | None = None
):
    """Thread-safe update of rate limit statistics."""
    key_hash = get_api_key_hash(api_key)
    with _cache_lock:
        if key_hash not in _rate_limits_cache:
            _rate_limits_cache[key_hash] = {}
        
        if remaining_req is not None:
            _rate_limits_cache[key_hash]["remaining_requests"] = remaining_req
        if reset_req is not None:
            _rate_limits_cache[key_hash]["reset_requests"] = reset_req
        if remaining_tokens is not None:
            _rate_limits_cache[key_hash]["remaining_tokens"] = remaining_tokens
        if reset_tokens is not None:
            _rate_limits_cache[key_hash]["reset_tokens"] = reset_tokens

def get_rate_limits(api_key: str | None) -> Dict[str, Any]:
    """Retrieve rate limits for the specified key hash."""
    key_hash = get_api_key_hash(api_key)
    with _cache_lock:
        limits = _rate_limits_cache.get(key_hash, {
            "remaining_requests": 14400,  # Default placeholder for standard tiers
            "reset_requests": "0s",
            "remaining_tokens": 180000,
            "reset_tokens": "0s"
        })
        return dict(limits)

# FastAPI Router to query rate limits
router = APIRouter(prefix="/api/v3/llm", tags=["LLM Rate Limits"])

@router.get("/rate-limits", response_model=dict)
async def query_rate_limits(
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key")
):
    """Retrieve the remaining requests and token limits for the active key."""
    from config.settings import settings
    effective_key = x_llm_api_key or settings.GROQ_API_KEY or "default"
    return get_rate_limits(effective_key)
