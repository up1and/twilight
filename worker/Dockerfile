# Worker-specific Dockerfile for satellite data processing and synchronization
FROM python:3.12-slim

# Configuration for satellite processing environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

# Install system dependencies for GIS and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev libgeos-dev libproj-dev \
    g++ make curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Speedy installation of common dependencies + [worker] extra using uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv pip install --system ".[worker]"

# Pre-download Pyspectral RSR data for satellite composite generation
RUN python -c "from pyspectral.utils import download_rsr; download_rsr()"

# Copy worker and support source code
COPY . .

# No exposed port for worker, it communicates outward to server/redis/minio
CMD ["python", "worker/main.py", "--worker"]
