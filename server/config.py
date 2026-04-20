import os
from dotenv import load_dotenv
from platformdirs import user_data_dir

load_dotenv()

def get_pycoast_dir():
    """Get pycoast data directory containing GSHHS and WDBII shapefiles.

    Returns:
        Path to pycoast data directory (parent of GSHHS_shp, WDBII_shp)
    """
    pycoast_dir = os.environ.get("PYCOAST_DATA_ROOT")
    if pycoast_dir and os.path.isdir(pycoast_dir):
        return pycoast_dir
    return user_data_dir("pycoast") 

# Server configuration with support for environment variables
# Primarily for MinIO and Redis connections
endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# Default Redis connection URL
redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# Auth key for API authentication
auth_key = os.getenv("AUTH_KEY", "twilight-secret")

# Available composite list, comma-separated
available_composites = os.getenv(
    "AVAILABLE_COMPOSITES", 
    "ir_clouds,true_color,ash,airmass,day_microphysics,night_microphysics,fog,convection,lower_vapor,upper_vapor"
).split(",")

# Task expiration days, 0 means no expiration
task_expire_days = int(os.getenv("TASK_EXPIRE_DAYS", 7))

# Sync expiration days, 0 means no expiration
sync_expire_days = int(os.getenv("SYNC_EXPIRE_DAYS", 30))
