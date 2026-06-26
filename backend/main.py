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

from contextlib import asynccontextmanager
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


# ─── Lifespan Context Manager ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    storage = Path(settings.STORAGE_DIR)
    storage.mkdir(parents=True, exist_ok=True)

    # Warn if production is running without persistent storage configured
    if settings.ENABLE_AUTH:  # Production mode
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

    # Start background cleanup task and keep a reference to it
    cleanup_task = asyncio.create_task(midnight_cleanup_scheduler())

    yield

    # --- Shutdown ---
    # Cancel the scheduler task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("⏰ Midnight cleanup scheduler task cancelled cleanly.")
    except Exception as e:
        logger.error("⏰ Error cancelling cleanup task: %s", e)

    # Close PostgreSQL Connection Pool
    try:
        from graph.graph import db_pool
        if db_pool is not None:
            logger.info("🔌 Gracefully closing PostgreSQL connection pool...")
            db_pool.close()
            logger.info("🔒 PostgreSQL connection pool closed successfully.")
    except Exception as e:
        logger.error("⚠️ Error while closing PostgreSQL pool during shutdown: %s", str(e))


# ─── App factory ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Data Analyst API",
    version="2.0.0",
    description="FastAPI backend with LangGraph orchestration and Vega-Lite visualization",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
@app.head("/health", tags=["System"])
async def health():
    """Extended health check with LLM and configuration diagnostics."""
    from utils.llm_factory import get_llm
    from pathlib import Path
    
    # Check LLM availability
    llm_ok = False
    llm_provider = "unknown"
    try:
        llm = get_llm("smart")
        llm_ok = llm is not None
        llm_provider = settings.SMART_PROVIDER if llm_ok else "none"
    except Exception:
        llm_ok = False
    
    # Check storage
    storage_path = Path(settings.STORAGE_DIR)
    storage_ok = storage_path.exists() and storage_path.is_dir()
    
    return {
        "status": "ok",
        "version": "2.0.0",
        "engine": "LangGraph + Vega-Lite",
        "config": {
            "auth_enabled": settings.ENABLE_AUTH,
            "llm_ready": llm_ok,
            "llm_provider": llm_provider,
            "llm_model": settings.SMART_MODEL,
            "groq_key_set": bool(settings.GROQ_API_KEY),
            "google_key_set": bool(settings.GOOGLE_API_KEY),
            "storage_dir": settings.STORAGE_DIR,
            "storage_accessible": storage_ok,
        }
    }


# ─── Midnight Cleanup Scheduler ───────────────────────────────────────────────
import asyncio
from datetime import datetime, timedelta
import shutil

def run_midnight_cleanup():
    """Wipes all user dataset files from physical storage and clears the dataset registry DB."""
    logger.info("🧹 Starting scheduled midnight cleanup...")
    
    # 1. Clean up database registry entries
    try:
        from services.dataset_service import get_dataset_service
        service = get_dataset_service()
        if hasattr(service, "delete_all_datasets"):
            service.delete_all_datasets()
            logger.info("🗑️ Cleared all dataset registry metadata from database.")
        else:
            logger.warning("⚠️ Dataset service does not implement delete_all_datasets.")
    except Exception as e:
        logger.error("❌ Failed to clean up database registry metadata: %s", e, exc_info=True)
        
    # 2. Clean up physical storage files
    try:
        storage_path = Path(settings.STORAGE_DIR)
        if storage_path.exists() and storage_path.is_dir():
            for item in storage_path.iterdir():
                # Preservation rule: Do NOT delete firebase-key.json
                if item.name == "firebase-key.json":
                    logger.debug("Preserving firebase-key.json in storage directory")
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                        logger.info("Deleted physical session directory: %s", item)
                    else:
                        item.unlink(missing_ok=True)
                        logger.info("Deleted physical file: %s", item)
                except Exception as file_exc:
                    logger.error("Failed to delete physical path %s: %s", item, file_exc)
            logger.info("🧹 Finished scheduled midnight cleanup of physical storage files.")
    except Exception as e:
        logger.error("❌ Failed to clean up physical storage files: %s", e, exc_info=True)

    # 3. Clean up all tracer traces
    try:
        from utils.tracer import tracer
        if hasattr(tracer, "clear_all"):
            count = tracer.clear_all()
            logger.info("🗑️ Cleared all %d trace records from tracer memory.", count)
        else:
            logger.warning("⚠️ Tracer does not implement clear_all.")
    except Exception as e:
        logger.error("❌ Failed to clean up tracer records: %s", e, exc_info=True)


async def midnight_cleanup_scheduler():
    """Async background task that triggers run_midnight_cleanup every night at 12:00 AM local time."""
    logger.info("⏰ Midnight cleanup scheduler task started.")
    while True:
        try:
            now = datetime.now()
            # Calculate next midnight (tomorrow at 12:00 AM local time)
            tomorrow = now.date() + timedelta(days=1)
            next_midnight = datetime.combine(tomorrow, datetime.min.time())
            
            seconds_until_midnight = (next_midnight - now).total_seconds()
            logger.info("⏰ Next midnight cleanup scheduled in %.2f seconds (at %s)", 
                        seconds_until_midnight, next_midnight.isoformat())
            
            await asyncio.sleep(seconds_until_midnight)
            run_midnight_cleanup()
        except asyncio.CancelledError:
            logger.info("⏰ Midnight cleanup scheduler task cancelled.")
            break
        except Exception as e:
            logger.error("❌ Error in midnight cleanup scheduler loop: %s", e, exc_info=True)
            await asyncio.sleep(60)


# (Startup and shutdown lifecycle events are handled by the lifespan context manager above)
