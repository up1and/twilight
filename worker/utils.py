import sys
import time
import datetime
import socket
import logging

from functools import wraps


def _replace_minute(time):
    minute = int(time.minute / 10) * 10
    return time.replace(minute=minute)

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

    _format = '[%(asctime)s] %(levelname)s %(message)s'
    formatter = logging.Formatter(_format)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    logger = logging.getLogger('tafor-layer')
    logger.setLevel(logLevel)
    logger.addHandler(ch)

    return logger


logger = createLogger(debug=True)
