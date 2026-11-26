import os
import sys
import time
import socket
import logging
import datetime

import numpy as np
from functools import wraps
from pyproj import CRS, Transformer


def _replace_minute(time):
    minute = int(time.minute / 10) * 10
    return time.replace(minute=minute, second=0, microsecond=0)

def _available_latest_time():
    utc = datetime.datetime.now(datetime.timezone.utc)
    time = _replace_minute(utc)
    return time - datetime.timedelta(minutes=20)


# Himawari-9 fixed 2 km full-disk grid: segment boundaries follow the curved
# scan lines, so a bbox is projected onto this grid instead of using latitude bands
ahi_full_disk = {
    "h": 35785863.0,
    "lon_0": 140.7,
    "a": 6378137.0,
    "b": 6356752.31,
    "extent": 5499999.901174725,
    "rows": 5500,
    "pixel_size": 2000.0,
    "segment_rows": 550,
}

to_ahi_geos = Transformer.from_crs(
    "EPSG:4326",
    CRS.from_dict({
        "proj": "geos",
        "h": ahi_full_disk["h"],
        "lon_0": ahi_full_disk["lon_0"],
        "a": ahi_full_disk["a"],
        "b": ahi_full_disk["b"],
    }),
    always_xy=True,
)


def bbox_segments(bbox):
    """AHI segment labels (e.g. "S01") whose 2 km scan lines cover bbox"""
    min_lon, min_lat, max_lon, max_lat = bbox
    lons = np.concatenate([
        np.linspace(min_lon, max_lon, 21), np.linspace(min_lon, max_lon, 21),
        np.full(9, min_lon), np.full(9, max_lon),
    ])
    lats = np.concatenate([
        np.full(21, min_lat), np.full(21, max_lat),
        np.linspace(min_lat, max_lat, 9), np.linspace(min_lat, max_lat, 9),
    ])
    _, y = to_ahi_geos.transform(lons, lats)
    # Points off the disk project to infinity; clipping saturates them at the
    # grid edges, which is exactly what the row extremes need
    rows = np.floor((ahi_full_disk["extent"] - y) / ahi_full_disk["pixel_size"])
    rows = np.clip(rows, 0, ahi_full_disk["rows"] - 1)
    first = int(rows.min() // ahi_full_disk["segment_rows"])
    last = int(rows.max() // ahi_full_disk["segment_rows"])
    segments = tuple("S{:02d}".format(i + 1) for i in range(first, last + 1))
    logger.debug(f"BBOX {bbox} maps to AHI segments {segments[0]}-{segments[-1]}")
    return segments

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
    
    def __init__(self, cache_dir, max_size=10, preserve=()):
        self.cache_dir = cache_dir
        self.max_size_bytes = int(max_size * 1024**3)
        self.preserve = {os.path.normpath(p) for p in preserve}

    def prune(self, dirpath, dirnames):
        """Drop preserved subtrees from os.walk."""
        dirnames[:] = [
            d for d in dirnames
            if os.path.normpath(os.path.join(dirpath, d)) not in self.preserve
        ]

    def get_cache_size(self):
        """Get the size of cache directory in bytes"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.cache_dir):
            self.prune(dirpath, dirnames)
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
        for dirpath, dirnames, filenames in os.walk(self.cache_dir):
            self.prune(dirpath, dirnames)
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
