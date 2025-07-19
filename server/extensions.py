"""
Flask extensions initialization
"""
import redis

from minio import Minio
from flask_caching import Cache

from config import endpoint, access_key, secret_key, redis_url

# Initialize Flask-Caching
cache = Cache()

# Configure Redis connection
redis_client = redis.from_url(redis_url, decode_responses=True)

# Initialize MinIO client
client = Minio(
    endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=False
)

def init_extensions(app):
    """Initialize Flask extensions"""
    # Configure Flask-Caching with RedisCache
    cache_config = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': redis_url,
        'CACHE_DEFAULT_TIMEOUT': 3600,  # 1 hour default cache timeout
        'CACHE_KEY_PREFIX': 'twilight_cache_'
    }
    app.config.update(cache_config)
    cache.init_app(app)
