# Use official lightweight Python 3.11 image
FROM python:3.11-slim

# Set system environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies (needed for compiling certain python binary extensions or pandas/numpy wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to utilize Docker build cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create a non-root group and user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

# Create storage directory and ensure it has correct permissions
RUN mkdir -p storage && chown -R appuser:appgroup storage

# Copy the rest of the application files
COPY . .

# Remove local venv and caches that should never be in the image
RUN rm -rf venv311 __pycache__ .env

# Change ownership of the entire /app directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose FastAPI service port
EXPOSE 8000

# Healthcheck configuration for container runners (ECS/Kubernetes/Docker Engine)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Run application in production using Gunicorn with Uvicorn workers
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main:app"]
