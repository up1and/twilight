import os
import sys
import time
import datetime
import socket
import logging

from functools import wraps


def _replace_minute(time):
    minute = int(time.minute / 10) * 10
    return time.replace(minute=minute, second=0, microsecond=0)

def _available_latest_time():
    utc = datetime.datetime.now(datetime.timezone.utc)
    time = _replace_minute(utc)
    return time - datetime.timedelta(minutes=20)

def get_local_ip():
    """Get local IP address"""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def generate_worker_id():
    """Generate worker ID from hostname and IP"""
    hostname = socket.gethostname()
    ip = get_local_ip()
    return f"{hostname}_{ip}"

def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time.time()
        result = f(*args, **kw)
        te = time.time()
        duration = te - ts

        # Log timing information
        logger.info(f"Function '{f.__name__}' completed in {duration:.2f}s")
        return result
    return wrap

def createLogger(debug=False):
    logLevel = logging.DEBUG if debug else logging.INFO

    _format = "[%(asctime)s] %(levelname)s %(message)s"
    formatter = logging.Formatter(_format)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    logger = logging.getLogger("tafor-layer")
    logger.setLevel(logLevel)
    logger.addHandler(ch)

    return logger


logger = createLogger(debug=True)


class CacheManager:
    """Simple cache manager with size limit functionality"""
    
    def __init__(self, cache_dir, max_size=10):
        self.cache_dir = cache_dir
        self.max_size_bytes = int(max_size * 1024**3)
    
    def get_cache_size(self):
        """Get the size of cache directory in bytes"""
        total_size = 0
        for dirpath, _, filenames in os.walk(self.cache_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    # Skip files that can't be accessed
                    continue
        return total_size
    
    def cleanup_cache(self):
        """Clean up cache directory to maintain size under limit using LRU strategy"""
        current_size = self.get_cache_size()
        if current_size <= self.max_size_bytes:
            return  # No cleanup needed

        # Get all files with their modification time
        files_with_mtime = []
        for dirpath, _, filenames in os.walk(self.cache_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    files_with_mtime.append((filepath, mtime))
                except (OSError, FileNotFoundError):
                    continue

        # Sort by modification time (oldest first)
        files_with_mtime.sort(key=lambda x: x[1])

        bytes_removed = 0
        files_removed = 0

        for file_path, _ in files_with_mtime:
            if current_size <= self.max_size_bytes:
                break
            try:
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                current_size -= file_size
                bytes_removed += file_size
                files_removed += 1
            except (OSError, FileNotFoundError):
                # Skip files that can't be removed
                continue

        if bytes_removed > 0:
            logger.info(f"Cache cleanup: Removed {bytes_removed} bytes from {files_removed} files "
                        f"(current: {current_size/(1024**3):.2f}GB")
