import os
from dotenv import load_dotenv

load_dotenv()

# MinIO endpoint for local raw data and processing results
endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# URL of the main server API
server_url = os.getenv("SERVER_URL", "http://127.0.0.1:5000")
# Authentication key for API requests
auth_key = os.getenv("AUTH_KEY", "twilight-secret")

# Task processor preferences
# Optional filtering for specific priorities or composites
# Priority filter: "high", "normal", "low"
priorities = [p.strip() for p in os.getenv("PRIORITIES", "").split(",") if p.strip()]
# Composite filter for task processor: "ir_clouds", "true_color", "ash", "airmass",
# "night_microphysics", "day_microphysics", 
# "fog", "convection", "vapor"
composites = [c.strip() for c in os.getenv("COMPOSITES", "").split(",") if c.strip()]
# Maximum resolution in meters (500, 1000, or 2000). Smaller value means higher resolution.
max_resolution = int(os.getenv("MAX_RESOLUTION", 1000))
# Region bounding box: [lon_min, lat_min, lon_max, lat_max]
bbox = [float(b.strip()) for b in os.getenv("BBOX", "75,0,160,55").split(",") if b.strip()]
# Available composite list, comma-separated, task generator
available_composites = os.getenv(
    "AVAILABLE_COMPOSITES", 
    "ir_clouds,true_color,ash,airmass,day_microphysics,night_microphysics,fog,convection,vapor"
).split(",")

# Maximum cache size in GB (default 200GB)
cache_size_limit = int(os.getenv("CACHE_SIZE_LIMIT", 200))

# Resampler algorithm (e.g., "nearest", "bilinear", "native")
resampler = os.getenv("RESAMPLER", "nearest")
# Estimated RAM consumption per worker in GB
mem_per_worker = float(os.getenv("MEM_PER_WORKER", 7.0))
# RAM to keep free for OS and other tasks in GB
system_margin = float(os.getenv("SYSTEM_MARGIN", 4.0))
