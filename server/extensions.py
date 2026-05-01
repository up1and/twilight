"""
Flask extensions initialization
"""
import redis
from minio import Minio
from flask_caching import Cache

from config import endpoint, access_key, secret_key, redis_url


class RQ:
    """Simple wrapper for RQ to provide Flask integration"""
    def __init__(self):
        self.connection = None

    def init_app(self, app):
        """
        Register the extension with the Flask application.
        
        :param app: The Flask application instance.
        """
        url = app.config.get("REDIS_URL", redis_url)
        self.connection = redis.from_url(url, decode_responses=False)
        app.extensions['rq'] = self

    def get_worker(self, *queues, **kwargs):
        """Return a worker for the given queues with the correct connection and context."""
        from rq import Worker
        from flask import current_app

        class FlaskWorker(Worker):
            def perform_job(self, job, queue, heartbeat_ttl=None):
                with current_app.app_context():
                    return super().perform_job(job, queue, heartbeat_ttl=heartbeat_ttl)

        return FlaskWorker(list(queues) or ['default'], connection=self.connection, **kwargs)

    def get_scheduler(self, **kwargs):
        """Return a CronScheduler instance with the correct connection"""
        from rq.cron import CronScheduler
        return CronScheduler(connection=self.connection, **kwargs)

    def job(self, *args, **kwargs):
        """Decorator to mark a function as an RQ job"""
        from rq.decorators import job
        
        # Ensure connection is always passed
        kwargs.setdefault('connection', self.connection)
        
        # Case: Used as @rq.job
        if len(args) == 1 and callable(args[0]):
            return job('default', **kwargs)(args[0])
        
        # Case: Used as @rq.job('queue_name') or with arguments
        return job(*args, **kwargs)


# Configure Redis connection
redis_client = redis.from_url(redis_url, decode_responses=True)

# Initialize Flask-Caching
cache = Cache()

# Initialize RQ
rq = RQ()

# Initialize MinIO client
client = Minio(
    endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=False
)

def init_extensions(app):
    """Initialize Flask extensions"""
    app.config["REDIS_URL"] = redis_url
    rq.init_app(app)

    # Configure Flask-Caching with RedisCache
    cache_config = {
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_URL": redis_url,
        "CACHE_DEFAULT_TIMEOUT": 3600,  # 1 hour default cache timeout
        "CACHE_KEY_PREFIX": "twilight_cache_"
    }
    app.config.update(cache_config)
    cache.init_app(app)
