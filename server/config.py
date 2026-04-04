import os

# Server configuration with support for environment variables
# Primarily for MinIO and Redis connections
endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# Default Redis connection URL
redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
