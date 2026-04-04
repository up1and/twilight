# Server-specific Dockerfile for Flask API and Tile service
FROM python:3.12-slim

# Configuration for GIS and Python environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARTOPY_USER_BACKGROUNDS=/root/.local/share/cartopy \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

# Install essential GIS libraries and FFmpeg for video snapshots
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev libgeos-dev libproj-dev \
    ffmpeg g++ make curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Speedy installation of common dependencies + [server] extra using uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv pip install --system ".[server]" gunicorn

# Pre-download Cartopy coastline data for map snapshots
RUN python -c "import cartopy.feature; cartopy.feature.COASTLINE.with_scale('10m')"

# Create mounted data directory
RUN mkdir -p /app/data

# Copy source code (data/ excluded via .dockerignore)
COPY . .

EXPOSE 5000

# Gunicorn server entrypoint for production-grade performance
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--worker-class", "gthread", "server.app:app"]
