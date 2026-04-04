import os

# MinIO endpoint for local raw data and processing results
endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# URL of the main server API
server_url = os.getenv("SERVER_URL", "http://127.0.0.1:5000")

# Task processor preferences
# Optional filtering for specific priorities or composites
processing_profile = {
    # Priority filter: "high", "normal", "low"
    "priorities": [],
    
    # Composite filter: "ir_clouds", "true_color", "ash", "night_microphysics"
    "composites": []
}

# Cache management settings
# Maximum cache size in GB (default 200GB)
cache_size_limit = int(os.getenv("CACHE_SIZE_LIMIT", "200"))
