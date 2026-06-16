import os
import json
import logging
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Production JSON log formatter for structured log parsing."""
    def __init__(self):
        super().__init__()

    def format(self, record):
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
        }
        
        # Capture tracebacks cleanly
        if record.exc_info:
            log_record["error_trace"] = self.formatException(record.exc_info)
            
        # Capture custom context injected dynamically (e.g. from middleware)
        for field in ("request_id", "method", "path", "client_ip", "status_code", "duration_sec"):
            if hasattr(record, field):
                log_record[field] = getattr(record, field)
                
        return json.dumps(log_record)


def setup_logging():
    """Configure system-wide log handlers depending on the environment."""
    from config.settings import settings
    
    root_logger = logging.getLogger()
    
    # Clean up existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    console_handler = logging.StreamHandler()
    
    if settings.ENABLE_AUTH:
        # Use structured JSON logging in production
        console_handler.setFormatter(JsonFormatter())
        root_logger.setLevel(logging.INFO)
    else:
        # Keep clean, color-readable console logs for development
        dev_formatter = logging.Formatter(
            fmt="%(asctime)s │ %(levelname)-7s │ %(name)-25s │ %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(dev_formatter)
        root_logger.setLevel(logging.INFO)
        
    root_logger.addHandler(console_handler)
    
    # Silence default uvicorn/httpx duplicate noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
