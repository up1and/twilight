# Worker-specific Dockerfile for satellite data processing and synchronization
FROM python:3.12-slim AS builder

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

# Copy uv and project definition
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml ./

# Install dependencies directly into system python
RUN uv pip install . gunicorn --no-cache -U && \
    rm -rf build/ *.egg-info/

# Pre-download Pyspectral RSR data for satellite composite generation
RUN python -c "from pyspectral.utils import download_rsr; download_rsr()"


FROM python:3.12-slim

# Configuration for satellite processing environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime libraries only (no -dev packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal36 libgeos-c1t64 libproj25 \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages, binaries and pyspectral data from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.local/share/pyspectral /root/.local/share/pyspectral

WORKDIR /app

# Copy worker source code
COPY . .

# No exposed port for worker, it communicates outward to server/redis/minio
CMD ["python", "main.py", "--worker"]
