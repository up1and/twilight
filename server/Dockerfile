# Server-specific Dockerfile for Flask API and Tile service
FROM python:3.12-slim AS builder

# Configuration for GIS and Python environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYCOAST_DATA_ROOT=/usr/local/share/pycoast \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

# Install essential GIS libraries and build tools for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev libgeos-dev libproj-dev \
    g++ make curl wget unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy uv and project definition
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml ./

# Install dependencies + gunicorn directly into system python
RUN uv pip install . gunicorn --no-cache -U && \
    rm -rf build/ *.egg-info/

# Pre-download GSHHS coastline data for pycoast
RUN mkdir -p $PYCOAST_DATA_ROOT && \
    wget -q https://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.3.7.zip -O /tmp/gshhs.zip && \
    unzip -q /tmp/gshhs.zip -d $PYCOAST_DATA_ROOT && \
    rm /tmp/gshhs.zip


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYCOAST_DATA_ROOT=/usr/local/share/pycoast

# Install runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal36 libgeos-c1t64 libproj25 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder $PYCOAST_DATA_ROOT $PYCOAST_DATA_ROOT

WORKDIR /app

# Copy source code
COPY . .

EXPOSE 5000

# Gunicorn server entrypoint for production-grade performance
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--worker-class", "gthread", "app:app"]
