# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

# System dependencies:
# - curl          : for the container HEALTHCHECK
# - libgl1        : OpenGL, required by OpenCV (a PaddleOCR dependency)
# - libglib2.0-0, libsm6, libxext6, libxrender1 : required by OpenCV/Paddle
# - libgomp1      : OpenMP, used by Paddle's CPU math kernels
#
# Note: poppler-utils is intentionally NOT installed — PDF pages are
# rendered with PyMuPDF (a pure Python wheel), so no external PDF binary
# is required.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so this layer is cached across code
# changes (only invalidated when requirements.txt changes).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY ocr_worker.py .

# Non-root user for security. The model cache dir is created and owned by
# this user up front so PaddleOCR can download/cache weights at runtime
# even when the dir is a mounted volume (see docker-compose.yml).
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/.paddle_cache \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    OCR_CACHE_DIR=/app/.paddle_cache

# Healthcheck hits the worker's internal HTTP server (see PAPERLESS_HEALTH_PORT)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PAPERLESS_HEALTH_PORT:-8080}/health || exit 1

CMD ["python", "-u", "ocr_worker.py"]
