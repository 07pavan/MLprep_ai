import os
import multiprocessing

# Bind address - Koyeb/Render pass the service port in the PORT env var
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Recommended workers: (2 * CPU Cores) + 1, custom-overrideable via WORKERS env var.
# Clamped to minimum 2 workers for concurrency in single-core environments.
cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv("WORKERS", max(2, cpu_count * 2 + 1)))

worker_class = "uvicorn.workers.UvicornWorker"

# Increase timeout to 120 seconds to accommodate longer-running LLM queries
# and complex dataset analysis tasks.
timeout = 120
keepalive = 5

# Logging configuration - output standard logs in structured style
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
