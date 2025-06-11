import os
import re
import uuid
import sqlite3
import datetime
import json

import redis

from flask import Flask, Response, request, jsonify
from flask_caching import Cache

from rio_tiler.io import Reader
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rasterio.errors import RasterioIOError

from minio import Minio
from minio.error import S3Error
from config import endpoint, access_key, secret_key, redis_url
from snapshot import (
    create_single_snapshot,
    create_series_snapshot,
    find_composite_object
)


TILE_SIZE = 256

app = Flask(__name__)

# Configure Flask-Caching with RedisCache
cache_config = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_REDIS_URL': redis_url,
    'CACHE_DEFAULT_TIMEOUT': 3600,  # 1 hour default cache timeout
    'CACHE_KEY_PREFIX': 'twilight_cache_'
}
app.config.update(cache_config)
cache = Cache(app)

# Configure Redis connection
redis_client = redis.from_url(redis_url, decode_responses=True)

# Custom JSON encoder function for datetime objects
def default_json_handler(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Configure Flask to use custom JSON encoder
app.json.default = default_json_handler

client = Minio(
    endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=False
)

available_composites = [
    'ir_clouds', 'true_color', 'ash', 'night_microphysics'
]

def upper_case(name):
    """
    Format composite name for display (e.g., "day_convection" to "Day Convection")
    """
    segments = name.split('_')
    formatted_segments = []
    
    for segment in segments:
        if len(segment) <= 2:
            formatted_segments.append(segment.upper())
        else:
            formatted_segments.append(segment[0].upper() + segment[1:].lower())
    
    return ' '.join(formatted_segments)

def parse_iso_timestamp(timestamp_str):
    """
    Parse an ISO 8601 timestamp string into a timezone-aware datetime object.
    """
    # Handle timezone-aware timestamps
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str.replace('Z', '+00:00')
    timestamp = datetime.datetime.fromisoformat(timestamp_str)
    # Ensure timezone-aware datetime
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
    
    return timestamp

# Task management
class Task:
    def __init__(self, composite, timestamp, priority='normal'):
        self.task_id = f"{composite}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.composite = composite
        self.timestamp = timestamp
        self.priority = priority
        self.status = 'pending'  # pending, processing, completed, failed
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.started = None
        self.completed = None
        self.worker_id = None
        self.error_message = None

    def __eq__(self, other):
        """Compare tasks based on composite and timestamp"""
        if not isinstance(other, Task):
            return False
        return (self.composite == other.composite and
                self.timestamp == other.timestamp)

    def __hash__(self):
        """Make Task hashable for use in sets and as dict keys"""
        return hash((self.composite, self.timestamp))

    @property
    def duration(self):
        """Calculate task duration in seconds"""
        if self.started and self.completed:
            return (self.completed - self.started).total_seconds()
        return None

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'composite': self.composite,
            'timestamp': self.timestamp,
            'priority': self.priority,
            'status': self.status,
            'created': self.created,
            'started': self.started if self.started else None,
            'completed': self.completed if self.completed else None,
            'duration': self.duration,
            'worker_id': self.worker_id,
            'error_message': self.error_message
        }

    def to_json(self):
        """Serialize task to JSON string for Redis storage"""
        data = self.to_dict()
        # Convert datetime objects to ISO format strings
        for key in ['timestamp', 'created', 'started', 'completed']:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str):
        """Deserialize task from JSON string"""
        data = json.loads(json_str)

        # Create task instance
        task = cls.__new__(cls)
        task.task_id = data['task_id']
        task.composite = data['composite']
        task.priority = data['priority']
        task.status = data['status']
        task.worker_id = data['worker_id']
        task.error_message = data['error_message']

        # Convert ISO format strings back to datetime objects
        task.timestamp = datetime.datetime.fromisoformat(data['timestamp'])
        task.created = datetime.datetime.fromisoformat(data['created'])
        task.started = datetime.datetime.fromisoformat(data['started']) if data['started'] else None
        task.completed = datetime.datetime.fromisoformat(data['completed']) if data['completed'] else None

        return task

class TaskManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        # Redis keys
        self.tasks_key = 'tasks'  # Hash: task_id -> task_json
        self.queue_key = 'task_queue'  # Sorted Set: task_id with priority+timestamp score
        self.expire_time = 3600 * 24 * 7  # 1 week

        # Redis lock for distributed locking
        self.lock = self.redis.lock('task_lock', timeout=10, blocking_timeout=10)

        # Priority weights for scoring (lower score = higher priority)
        self.priority_weights = {'high': 0, 'normal': 1000000, 'low': 2000000}

    def _calculate_score(self, task):
        """Calculate score for sorted set (lower score = higher priority)"""
        priority_weight = self.priority_weights.get(task.priority, 1000000)
        # Use timestamp as seconds since epoch for fine-grained ordering
        timestamp_score = int(task.timestamp.timestamp())
        return priority_weight + timestamp_score

    def create_task(self, composite, timestamp, priority='normal'):
        """Create a new task with deduplication and optional priority promotion"""
        with self.lock:
            # Create a temporary task for comparison
            temp_task = Task(composite, timestamp, priority)

            # Check for existing task using __eq__ method
            existing_tasks = self._get_all_tasks()
            for existing_task in existing_tasks:
                if (existing_task == temp_task and
                    existing_task.status in ['pending', 'processing']):
                    # Task already exists, return existing task
                    return existing_task

            # Create new task if no duplicate found
            task = temp_task

            # Store task in Redis
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())

            # Add to sorted set with calculated score
            score = self._calculate_score(task)
            self.redis.zadd(self.queue_key, {task.task_id: score})

            # If this is a monitor mode task with normal priority, promote older pending normal tasks
            if priority == 'normal':
                self._promote_tasks_in_queue(timestamp)

            self.redis.expire(self.tasks_key, self.expire_time)
            return task

    def _get_all_tasks(self):
        """Get all tasks from Redis"""
        task_data = self.redis.hgetall(self.tasks_key)
        tasks = []
        for task_json in task_data.values():
            tasks.append(Task.from_json(task_json))
        return tasks

    def _promote_tasks_in_queue(self, reference_timestamp):
        """Promote pending normal priority tasks in queue older than reference timestamp to high priority"""
        # Note: This method is called within the create_task lock, so no additional locking needed

        # Get all task IDs from the queue
        task_ids = self.redis.zrange(self.queue_key, 0, -1)

        # Process tasks that need promotion
        promoted_tasks = []
        for task_id in task_ids:
            task_json = self.redis.hget(self.tasks_key, task_id)
            if task_json:
                task = Task.from_json(task_json)
                if (task.priority == 'normal' and
                    task.timestamp < reference_timestamp):
                    task.priority = 'high'
                    promoted_tasks.append(task)

        # Update promoted tasks
        for task in promoted_tasks:
            # Update task data
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())
            # Update score in sorted set
            new_score = self._calculate_score(task)
            self.redis.zadd(self.queue_key, {task.task_id: new_score})

    def get_task(self, task_id):
        """Get task by ID"""
        task_json = self.redis.hget(self.tasks_key, task_id)
        if task_json:
            return Task.from_json(task_json)
        return None

    def get_next_task(self, worker_id):
        """Get next pending task for worker"""
        with self.lock:
            # Get the task with lowest score (highest priority)
            task_ids = self.redis.zrange(self.queue_key, 0, 0)
            if not task_ids:
                return None

            task_id = task_ids[0]

            # Check if task still exists
            task_json = self.redis.hget(self.tasks_key, task_id)
            if not task_json:
                # Task was deleted, remove from queue
                self.redis.zrem(self.queue_key, task_id)
                return None

            task = Task.from_json(task_json)
            task.status = 'processing'
            task.started = datetime.datetime.now(datetime.timezone.utc)
            task.worker_id = worker_id

            # Remove from queue and update task status
            self.redis.zrem(self.queue_key, task_id)
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())

            return task

    def update_task_status(self, task_id, status, error_message=None):
        """Update task status"""
        with self.lock:
            task_json = self.redis.hget(self.tasks_key, task_id)
            if not task_json:
                return False

            task = Task.from_json(task_json)
            task.status = status
            if error_message:
                task.error_message = error_message
            if status in ['completed', 'failed']:
                task.completed = datetime.datetime.now(datetime.timezone.utc)

            # Update task in Redis
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())
            self.redis.expire(self.tasks_key, self.expire_time)
            return True

    def get_tasks(self, status=None, composite=None, limit=20, offset=0):
        """Get tasks with optional filtering"""
        all_tasks = self._get_all_tasks()
        filtered_tasks = []

        for task in all_tasks:
            if status and task.status != status:
                continue
            if composite and task.composite != composite:
                continue
            filtered_tasks.append(task)

        # Sort by created desc
        filtered_tasks.sort(key=lambda t: t.created, reverse=True)

        return filtered_tasks[offset:offset+limit], len(filtered_tasks)

# Global task manager
task_manager = TaskManager(redis_client)

def extract_timestamp_from_object_name(object_name):
    """
    Extract timestamp from object name
    Expected format: composite/YYYY/MM/DD/himawari_composite_YYYYMMDD_HHMM.tif
    """
    match = re.search(r'_(\d{8})_(\d{4})\.tif$', object_name)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        try:
            # Parse datetime and set UTC timezone
            dt = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
            return dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            app.logger.warning(f"Failed to parse timestamp from {object_name}")
    return None

def extract_composite_from_object_name(object_name):
    """
    Extract composite name from object name
    """
    # Try to extract from the filename
    for composite in available_composites:
        if f"himawari_{composite}_" in object_name:
            return composite

    return None

# Dictionary to store the latest update time for each composite
composite_state = {composite: None for composite in available_composites}

def initialize_composite_state():
    """
    Initialize composite_state with the latest objects from MinIO
    """
    app.logger.info("Initializing composite state...")

    # Get all objects from MinIO in one call
    try:
        objects = list(client.list_objects('himawari', recursive=True))
        # Group objects by composite
        composite_objects = {}
        for obj in objects:
            composite_name = extract_composite_from_object_name(obj.object_name)
            if composite_name and composite_name in available_composites:
                if composite_name not in composite_objects:
                    composite_objects[composite_name] = []
                composite_objects[composite_name].append(obj)

        # Find the latest timestamp for each composite
        for composite, objects in composite_objects.items():
            latest_timestamp = None

            for obj in objects:
                timestamp = extract_timestamp_from_object_name(obj.object_name)
                if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                    latest_timestamp = timestamp

            if latest_timestamp:
                composite_state[composite] = latest_timestamp
                app.logger.info(f"Found latest timestamp for {composite}: {latest_timestamp}")
            else:
                app.logger.info(f"No valid timestamp found for {composite}")

    except Exception as e:
        app.logger.error(f"Error initializing composite state: {str(e)}")


initialize_composite_state()

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

    # Add HTTP cache headers for tile and tilejson responses
    if response.status_code == 200:
        if request.endpoint == 'tile' and response.mimetype == 'image/png' or \
            request.endpoint == 'natural_earth_tile' and response.mimetype == 'application/x-protobuf':
            # Cache pbf tiles for 12 hours (43200 seconds)
            response.headers['Cache-Control'] = 'public, max-age=43200'
            response.headers['Expires'] = (datetime.datetime.now(datetime.timezone.utc) +
                                         datetime.timedelta(hours=12)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        elif request.endpoint == 'tilejson' and response.mimetype == 'application/json':
            # Cache tilejson for 1 hour (3600 seconds)
            response.headers['Cache-Control'] = 'public, max-age=3600'
            response.headers['Expires'] = (datetime.datetime.now(datetime.timezone.utc) +
                                         datetime.timedelta(hours=1)).strftime('%a, %d %b %Y %H:%M:%S GMT')

    return response

def find_tile(composite, z, x, y, timestamp=None):
    """
    Common function to handle tile requests with or without time parameter
    """
    if composite not in available_composites:
        error_msg = {
            "error": "Not Found",
            "message": f"Composite {composite} not available",
            "available_composites": available_composites
        }
        return jsonify(error_msg), 404

    try:
        object_name = find_composite_object(composite, timestamp)

        try:
            presigned_url = client.presigned_get_object(
                bucket_name='himawari',
                object_name=object_name,
                expires=datetime.timedelta(hours=24)
            )

            with Reader(presigned_url) as cog:
                img = cog.tile(x, y, z, tilesize=256)
                if composite == 'ir_clouds':
                    cm = cmap.get('rdgy')
                    content = img.render(colormap=cm)
                else:
                    content = img.render()
                return Response(content, mimetype="image/png")

        except TileOutsideBounds:
            app.logger.warning(f"Tile {z}/{x}/{y} is outside data bounds")
            error_msg = {
                "error": "Tile Outside Bounds",
                "message": f"Tile {z}/{x}/{y} is outside data bounds",
                "tile": {"z": z, "x": x, "y": y}
            }
            return jsonify(error_msg), 404

        except RasterioIOError as e:
            app.logger.error(f"Rasterio IO error for tile {z}/{x}/{y}: {str(e)}", exc_info=True)
            error_msg = {
                "error": "Rasterio IO Error",
                "message": f"Error reading raster data: {str(e)}",
                "tile": {"z": z, "x": x, "y": y}
            }
            return jsonify(error_msg), 500

        except Exception as e:
            app.logger.error(f"Error generating tile {z}/{x}/{y}: {str(e)}", exc_info=True)
            error_msg = {
                "error": "Internal Server Error",
                "message": f"Error generating tile: {str(e)}",
                "tile": {"z": z, "x": x, "y": y}
            }
            return jsonify(error_msg), 500

    except S3Error as e:
        app.logger.error(f"S3 error for {composite} at time {timestamp}: {str(e)}", exc_info=True)
        error_msg = {
            "error": "S3 Error",
            "message": f"Error accessing object storage: {str(e)}",
            "composite": composite,
            "time": timestamp if timestamp else None
        }
        return jsonify(error_msg), 500

@app.route("/<composite>/tiles/<timestamp>/<int:z>/<int:x>/<int:y>.png")
@cache.cached(timeout=43200)  # Cache for 12 hours
def tile(composite, timestamp, z, x, y):
    """
    Tile request with ISO 8601 time format
    test url: http://localhost:5000/ash/tiles/2025-04-20T04:00:00/5/25/15.png
    """
    try:
        request_time = parse_iso_timestamp(timestamp)
        return find_tile(composite, z, x, y, request_time)
    except ValueError:
        error_msg = {
            "error": "Invalid Time Format",
            "message": "Invalid time format. Please use ISO 8601 format (e.g., 2023-04-20T04:00:00)",
            "provided_time": timestamp
        }
        return jsonify(error_msg), 400

@app.route('/<composite>.tilejson')
@cache.cached(timeout=3600)  # Cache for 1 hour
def tilejson(composite):
    if composite not in available_composites:
        error_msg = {
            "error": "Not Found",
            "message": f"Composite {composite} not available",
            "available_composites": available_composites
        }
        return jsonify(error_msg), 404

    try:
        timestamp = composite_state.get(composite)
        object_name = find_composite_object(composite, timestamp)

        try:
            presigned_url = client.presigned_get_object(
                bucket_name='himawari',
                object_name=object_name,
                expires=datetime.timedelta(hours=24)
            )
            with Reader(presigned_url) as cog:
                # Define attribution for different composites
                name = upper_case(composite)
                return jsonify({
                    "bounds": cog.get_geographic_bounds(cog.tms.rasterio_geographic_crs),
                    "minzoom": cog.minzoom,
                    "maxzoom": cog.maxzoom,
                    "name": f"Himawari {name}",
                    "attribution": f"© Himawari {name}",
                    "tiles": [
                        f"{request.host_url.rstrip('/')}/{composite}/tiles/{'{time}'}/{'{z}'}/{'{x}'}/{'{y}'}.png"
                    ]
                })

        except RasterioIOError as e:
            app.logger.error(f"Rasterio IO error for tilejson {composite}: {str(e)}", exc_info=True)
            error_msg = {
                "error": "Rasterio IO Error",
                "message": f"Error reading raster data: {str(e)}",
                "composite": composite
            }
            return jsonify(error_msg), 500

        except Exception as e:
            app.logger.error(f"Error generating tilejson for {composite}: {str(e)}", exc_info=True)
            error_msg = {
                "error": "Internal Server Error",
                "message": f"Error generating tilejson: {str(e)}",
                "composite": composite
            }
            return jsonify(error_msg), 500

    except S3Error as e:
        app.logger.error(f"S3 error for {composite}: {str(e)}", exc_info=True)
        error_msg = {
            "error": "S3 Error",
            "message": f"Error accessing object storage: {str(e)}",
            "composite": composite
        }
        return jsonify(error_msg), 500

@app.route('/lands/<int:z>/<int:x>/<int:y>.pbf')
@cache.cached(timeout=43200)  # Cache for 12 hours
def natural_earth_tile(z, x, y):
    """
    Serve vector tiles from natural_earth.mbtiles
    """
    # Validate tile coordinates
    if not (0 <= z <= 18):
        return jsonify({
            'error': 'Bad Request',
            'message': 'Invalid zoom level. Must be between 0 and 18'
        }), 400

    max_coord = 2 ** z
    if not (0 <= x < max_coord) or not (0 <= y < max_coord):
        return jsonify({
            'error': 'Bad Request',
            'message': f'Invalid tile coordinates for zoom level {z}'
        }), 400

    mbtiles_path = os.path.join(os.path.dirname(__file__), 'natural_earth.mbtiles')

    if not os.path.exists(mbtiles_path):
        return jsonify({
            'error': 'Not Found',
            'message': 'natural_earth.mbtiles file not found'
        }), 404

    try:
        conn = sqlite3.connect(mbtiles_path)
        cursor = conn.cursor()

        # Convert TMS y to XYZ y
        tms_y = (1 << z) - 1 - y

        # Use parameterized query to prevent SQL injection
        cursor.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
            (z, x, tms_y)
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            response = Response(result[0], mimetype='application/x-protobuf')
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Content-Encoding'] = 'gzip'
            return response
        else:
            return Response('', status=204)  # No content

    except Exception as e:
        app.logger.error(f"Error serving lands tile {z}/{x}/{y}: {str(e)}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500

@app.route('/')
def index():
    """
    Provide basic server information and instructions for use
    """
    info = {
        "status": "running",
        "description": "Himawari Tile Server",
        "available_composites": available_composites,
        "usage": {
            "tiles": {
                "standard": "/{composite}/tiles/{time}/{z}/{x}/{y}.png (ISO 8601 time format)"
            },
            "tilejson": "/{composite}.tilejson",
            "latest_times": "/composites/latest"
        },
        "examples": {
            "standard_tile": f"/{available_composites[0]}/tiles/2025-04-20T04:00:00/5/25/15.png",
            "tilejson": f"/{available_composites[0]}.tilejson",
            "latest_times": "/composites/latest"
        }
    }
    return jsonify(info)


@app.route('/minio/events', methods=['GET', 'POST'])
def minio_event():
    """
    Handle MinIO events for object creation/update (legacy fallback)
    """
    if request.method == 'POST':
        try:
            event = request.get_json()
            object_key = event.get('Key', '')
            # Split bucket name and object name
            parts = object_key.split('/', 1)
            if len(parts) < 2:
                return jsonify({"error": "Invalid Key format"}), 400

            _, object_name = parts

            composite_name = extract_composite_from_object_name(object_name)
            timestamp = extract_timestamp_from_object_name(object_name)
            if composite_name and timestamp:
                # Only update if the timestamp is newer than what we have
                current_timestamp = composite_state.get(composite_name)
                if current_timestamp is None or timestamp > current_timestamp:
                    # Update composite_state with the new timestamp
                    composite_state[composite_name] = timestamp
                    app.logger.info(f"Updated state via MinIO event for {composite_name}: {timestamp}")

            return jsonify(event), 201

        except Exception as e:
            app.logger.error(f"Error processing MinIO event: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    else:
        # GET request - return service status and composite state
        result = {
            'live': datetime.datetime.now(datetime.timezone.utc),
        }
        return jsonify(result)


@app.route('/composites/latest', methods=['GET'])
def latest_composite_state():
    """
    Get the latest update time for all composites
    """
    return jsonify(composite_state)

# Task Management API Routes

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new processing task"""
    try:
        data = request.get_json()

        # Validate required fields
        if not data or 'composite' not in data or 'timestamp' not in data:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Missing required fields: composite, timestamp'
            }), 400

        composite = data['composite']
        if composite not in available_composites:
            return jsonify({
                'error': 'Bad Request',
                'message': f'Invalid composite. Available: {available_composites}'
            }), 400

        # Parse timestamp
        try:
            timestamp = parse_iso_timestamp(data['timestamp'])
        except ValueError:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Invalid timestamp format. Use ISO 8601 format'
            }), 400

        priority = data.get('priority', 'normal')
        if priority not in ['low', 'normal', 'high']:
            priority = 'normal'

        # Create task
        task = task_manager.create_task(composite, timestamp, priority)

        return jsonify({
            'task_id': task.task_id,
            'status': task.status,
            'created': task.created
        }), 201

    except Exception as e:
        app.logger.error(f"Error creating task: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get task details by ID"""
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({
            'error': 'Not Found',
            'message': f'Task {task_id} not found'
        }), 404

    return jsonify(task.to_dict())


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get tasks with optional filtering"""
    try:
        status = request.args.get('status')
        composite = request.args.get('composite')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # Max 100 per page

        offset = (page - 1) * per_page
        tasks, total = task_manager.get_tasks(status, composite, per_page, offset)

        return jsonify({
            'tasks': [task.to_dict() for task in tasks],
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        })

    except ValueError:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Invalid page or per_page parameter'
        }), 400
    except Exception as e:
        app.logger.error(f"Error getting tasks: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@app.route('/api/tasks/next', methods=['GET'])
def get_next_task():
    """Get next pending task for worker"""
    worker_id = request.args.get('worker_id')
    if not worker_id:
        return jsonify({
            'error': 'Bad Request',
            'message': 'worker_id parameter is required'
        }), 400

    task = task_manager.get_next_task(worker_id)
    if not task:
        return jsonify({
            'message': 'No pending tasks'
        }), 204  # No Content

    return jsonify({
        'task_id': task.task_id,
        'composite': task.composite,
        'timestamp': task.timestamp
    })


@app.route('/api/tasks/<task_id>/status', methods=['PUT'])
def update_task_status(task_id):
    """Update task status"""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Missing required field: status'
            }), 400

        status = data['status']
        if status not in ['pending', 'processing', 'completed', 'failed']:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Invalid status. Must be: pending, processing, completed, failed'
            }), 400

        error_message = data.get('error_message')

        success = task_manager.update_task_status(task_id, status, error_message)
        if not success:
            return jsonify({
                'error': 'Not Found',
                'message': f'Task {task_id} not found'
            }), 404

        # Get task details before updating status
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({
                'error': 'Not Found',
                'message': f'Task {task_id} not found'
            }), 404

        # Update composite_state when task is completed
        if status == 'completed':
            composite_name = task.composite
            timestamp = task.timestamp

            # Only update if this timestamp is newer than what we have
            current_timestamp = composite_state.get(composite_name)
            if current_timestamp is None or timestamp > current_timestamp:
                composite_state[composite_name] = timestamp
                app.logger.info(f"Updated composite state via task completion: {composite_name} -> {timestamp}")

        return jsonify({
            'message': 'Task status updated successfully'
        })

    except Exception as e:
        app.logger.error(f"Error updating task status: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@app.route('/api/snapshots', methods=['POST'])
def create_snapshot():
    """Create a snapshot image or video with geographic bounds and coastlines"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['bbox', 'timestamp', 'composite']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': 'Bad Request',
                    'message': f'Missing required field: {field}'
                }), 400

        bbox = data['bbox']
        timestamp = data['timestamp']
        composite = data['composite']
        timedelta_minutes = data.get('timedelta')  # Optional time delta in minutes

        # Validate bbox format
        if not isinstance(bbox, list) or len(bbox) != 4:
            return jsonify({
                'error': 'Bad Request',
                'message': 'bbox must be an array of 4 numbers [min_lng, min_lat, max_lng, max_lat]'
            }), 400

        # Validate composite
        if composite not in available_composites:
            return jsonify({
                'error': 'Bad Request',
                'message': f'Invalid composite. Available: {available_composites}'
            }), 400

        # Parse timestamps
        try:
            start_time = parse_iso_timestamp(timestamp)
        except ValueError:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Invalid timestamp format. Use ISO 8601 format'
            }), 400

        if timedelta_minutes:
            # Validate timedelta
            if not isinstance(timedelta_minutes, (int, float)) or timedelta_minutes <= 0:
                return jsonify({
                    'error': 'Bad Request',
                    'message': 'timedelta must be a positive number (minutes)'
                }), 400

            # Validate time range (max 24 hours = 1440 minutes)
            if timedelta_minutes > 1440:
                return jsonify({
                    'error': 'Bad Request',
                    'message': 'Time range cannot exceed 24 hours (1440 minutes)'
                }), 400

            # Calculate end time
            end_time = start_time + datetime.timedelta(minutes=timedelta_minutes)

        # Create video from time range
        if timedelta_minutes:
            result = create_series_snapshot(client, composite, start_time, end_time, bbox, task_manager)
        else:
            # Create single snapshot
            result = create_single_snapshot(client, composite, start_time, bbox, task_manager)

        if result['status'] == 'processing':
            return jsonify(result), 202
        else:
            return jsonify(result)

    except Exception as e:
        app.logger.error(f"Error in create_snapshot: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    import logging
    # Set logging level to INFO to see debug messages
    app.logger.setLevel(logging.INFO)

    # Create console handler and set level to INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Add handler to app logger
    app.logger.addHandler(console_handler)

    app.run(host='0.0.0.0', port=5000, debug=True)
