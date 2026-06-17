"""FastAPI application entry point"""
from __future__ import annotations
import logging
import os
import base64
from pathlib import Path

from utils.logging_config import setup_logging

# Initialize structured JSON logging for production, dev-friendly log for local
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Sentry SDK for error monitoring in production if configured
from config.settings import settings
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        
        def before_send(event, hint):
            # Scrub sensitive authentication headers before sending to Sentry
            if "request" in event:
                req = event["request"]
                if "headers" in req:
                     headers = req["headers"]
                     for k in list(headers.keys()):
                         if k.lower() in ("authorization", "cookie", "set-cookie", "x-api-key"):
                             headers[k] = "[REDACTED]"
            return event
            
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            send_default_pii=False,
            before_send=before_send,
            environment="production" if settings.ENABLE_AUTH else "development"
        )
        logger.info("🛡️ Sentry SDK initialized for production error monitoring (PII redacted)")
    except Exception as e:
        logger.error("❌ Failed to initialize Sentry SDK: %s", e)

from config.settings import settings

# ─── Decode Firebase credentials immediately (before importing routers/graph) ───
if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
    try:
        storage = Path(settings.STORAGE_DIR)
        storage.mkdir(parents=True, exist_ok=True)
        key_data = base64.b64decode(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
        key_file = storage / "firebase-key.json"
        key_file.write_bytes(key_data)
        
        # Override GOOGLE_APPLICATION_CREDENTIALS internally to ensure we use this decoded file
        settings.GOOGLE_APPLICATION_CREDENTIALS = str(key_file.resolve())
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
        logger.info("🔥 Decoded and saved Firebase Service Account JSON to %s (overriding GOOGLE_APPLICATION_CREDENTIALS)", settings.GOOGLE_APPLICATION_CREDENTIALS)
    except Exception as e:
        logger.error("❌ Failed to decode FIREBASE_SERVICE_ACCOUNT_JSON: %s", e)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.upload import router as upload_router
from routers.chat import router as chat_router
from routers.clean import router as clean_router
from routers.traces import router as traces_router
from routers.insights import router as insights_router
from routers.profiling import router as profiling_router
from routers.datasets import router as datasets_router
from routers.cleaning import router as cleaning_plan_router    # Phase 2A — session-based
from routers.cleaning_v1 import router as cleaning_v1_router   # Phase 2A v1 — REST path params
from routers.chat_copilot import router as chat_copilot_router
from routers.explanation import router as explanation_router
from routers.insight import router as insight_router
from routers.visualization import router as visualization_router
from routers.story import router as story_router
from routers.imports import router as imports_router
from utils.llm_middleware import LLMContextMiddleware
from utils.rate_limit_tracker import router as rate_limit_router


# ─── App factory ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Data Analyst API",
    version="2.0.0",
    description="FastAPI backend with LangGraph orchestration and Vega-Lite visualization",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Custom LLM context propagation middleware ─────────────────────────────
app.add_middleware(LLMContextMiddleware)

# ─── Structured Logging & Request Context Middleware ──────────────────────────
import uuid
import time
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    status_code = response.status_code
    
    log_extra = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "client_ip": client_ip,
        "status_code": status_code,
        "duration_sec": round(duration, 4)
    }
    
    logger.info(
        f"API Request: {method} {path} processed in {duration:.4f}s with status {status_code}",
        extra=log_extra
    )
    
    response.headers["X-Request-ID"] = request_id
    return response


# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(clean_router)
app.include_router(traces_router)
app.include_router(insights_router)
app.include_router(profiling_router)
app.include_router(datasets_router)
app.include_router(cleaning_plan_router)   # Phase 2A — session-based plan endpoints
app.include_router(cleaning_v1_router)     # Phase 2A v1 — REST path-param plan endpoints
app.include_router(chat_copilot_router)
app.include_router(explanation_router)
app.include_router(insight_router)
app.include_router(visualization_router)
app.include_router(story_router)
app.include_router(imports_router)
app.include_router(rate_limit_router)



# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "engine": "LangGraph + Vega-Lite",
    }


# ─── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    storage = Path(settings.STORAGE_DIR)
    storage.mkdir(parents=True, exist_ok=True)

    # Warn if production is running without persistent storage configured
    if settings.ENABLE_AUTH:  # Production mode
        # Check if the storage directory is the default relative/ephemeral directory
        from config.settings import BACKEND_DIR
        default_storage_dir = str(BACKEND_DIR / "storage")
        if settings.STORAGE_DIR == default_storage_dir:
            logger.warning(
                "⚠️ WARNING: Production is running with default ephemeral storage (%s). "
                "Uploaded datasets will be lost on container restart or scale-down. "
                "Please configure a Render Persistent Disk and set STORAGE_DIR=/app/storage.",
                settings.STORAGE_DIR
            )

    # Initialize Firebase Admin SDK
    import firebase_admin
    from firebase_admin import credentials
    if not firebase_admin._apps:
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            try:
                cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
                firebase_admin.initialize_app(cred)
                logger.info("🔥 Firebase Admin SDK initialized with certificate")
            except Exception as e:
                logger.error("❌ Failed to initialize Firebase Admin with certificate: %s", e)
        else:
            try:
                firebase_admin.initialize_app()
                logger.info("🔥 Firebase Admin SDK initialized with default credentials")
            except Exception as e:
                logger.warning("⚠️ Firebase Admin SDK initialized without credentials (ENABLE_AUTH must be False to allow local calls): %s", e)

    logger.info("🚀 AI Data Analyst API v2.0.0 started")
    logger.info("   Storage  : %s", storage.resolve())
    logger.info("   Docs     : http://localhost:8000/docs")
    logger.info("   CORS     : %s", settings.CORS_ORIGINS)


# ─── Shutdown ─────────────────────────────────────────────────────────────────
@app.on_event("shutdown")
async def on_shutdown():
    try:
        from graph.graph import db_pool
        if db_pool is not None:
            logger.info("🔌 Gracefully closing PostgreSQL connection pool...")
            db_pool.close()
            logger.info("🔒 PostgreSQL connection pool closed successfully.")
    except Exception as e:
        logger.error("⚠️ Error while closing PostgreSQL pool during shutdown: %s", str(e))
