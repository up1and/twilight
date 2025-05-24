import datetime
import re
import uuid
import threading
from collections import deque

from flask import Flask, Response, request, jsonify
from rio_tiler.io import Reader
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rasterio.errors import RasterioIOError

from minio import Minio
from minio.error import S3Error
from config import endpoint, access_key, secret_key


TILE_SIZE = 256

app = Flask(__name__)
client = Minio(
    endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=False
)

available_composites = [
    'ir_clouds', 'true_color', 'ash', 'night_microphysics'
]

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

class TaskManager:
    def __init__(self):
        self.tasks = {}  # task_id -> Task
        self.task_queue = deque()  # pending tasks
        self.lock = threading.Lock()

    def create_task(self, composite, timestamp, priority='normal'):
        """Create a new task with deduplication and optional priority promotion"""
        with self.lock:
            # Create a temporary task for comparison
            temp_task = Task(composite, timestamp, priority)

            # Check for existing task using __eq__ method
            for existing_task in self.tasks.values():
                if (existing_task == temp_task and
                    existing_task.status in ['pending', 'processing']):
                    # Task already exists, return existing task
                    return existing_task

            # Create new task if no duplicate found
            task = temp_task
            self.tasks[task.task_id] = task

            # If this is a monitor mode task with normal priority, promote older pending normal tasks
            if priority == 'normal':
                self._promote_tasks_in_queue(timestamp)

            # Add task to queue with smart insertion
            self._insert_task_to_queue(task)

            return task

    def _promote_tasks_in_queue(self, reference_timestamp):
        """Promote pending normal priority tasks in queue older than reference timestamp to high priority"""

        # Iterate through queue and promote tasks (queue contains Task objects now)
        for task in self.task_queue:
            if (task.priority == 'normal' and
                task.timestamp < reference_timestamp):
                task.priority = 'high'

        # Re-sort queue to reflect new priorities
        self._sort_queue()

    def _insert_task_to_queue(self, task):
        """Insert task to queue at the correct position based on priority and timestamp"""
        if not self.task_queue:
            self.task_queue.append(task)
            return

        # Find the correct position to insert
        priority_order = {'high': 0, 'normal': 1, 'low': 2}
        task_priority_value = priority_order.get(task.priority, 1)

        insert_index = len(self.task_queue)  # Default to end

        for i, existing_task in enumerate(self.task_queue):
            existing_priority_value = priority_order.get(existing_task.priority, 1)

            # If new task has higher priority, insert here
            if task_priority_value < existing_priority_value:
                insert_index = i
                break
            # If same priority, compare timestamps (earlier first)
            elif (task_priority_value == existing_priority_value and
                  task.timestamp < existing_task.timestamp):
                insert_index = i
                break

        # Insert at the found position
        self.task_queue.insert(insert_index, task)

    def _sort_queue(self):
        """Sort the existing queue by priority and timestamp"""
        priority_order = {'high': 0, 'normal': 1, 'low': 2}

        def sort_key(task):
            return (priority_order.get(task.priority, 1), task.timestamp)

        # Convert to list, sort, and convert back to deque
        sorted_tasks = sorted(list(self.task_queue), key=sort_key)
        self.task_queue.clear()
        self.task_queue.extend(sorted_tasks)

    def get_task(self, task_id):
        """Get task by ID"""
        return self.tasks.get(task_id)

    def get_next_task(self, worker_id):
        """Get next pending task for worker"""
        with self.lock:
            while self.task_queue:
                task = self.task_queue.popleft()
                task.status = 'processing'
                task.started = datetime.datetime.now(datetime.timezone.utc)
                task.worker_id = worker_id
                return task
                # If task is not pending, continue to next task
            return None

    def update_task_status(self, task_id, status, error_message=None):
        """Update task status"""
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = status
                if error_message:
                    task.error_message = error_message
                if status in ['completed', 'failed']:
                    task.completed = datetime.datetime.now(datetime.timezone.utc)
                return True
            return False

    def get_tasks(self, status=None, composite=None, limit=20, offset=0):
        """Get tasks with optional filtering"""
        filtered_tasks = []
        for task in self.tasks.values():
            if status and task.status != status:
                continue
            if composite and task.composite != composite:
                continue
            filtered_tasks.append(task)

        # Sort by created desc
        filtered_tasks.sort(key=lambda t: t.created, reverse=True)

        return filtered_tasks[offset:offset+limit], len(filtered_tasks)

# Global task manager
task_manager = TaskManager()

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
            return datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
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

def find_composite_object(composite, timestamp=None):
    """
    Find the object name for a composite, either for a specific time or the latest
    """
    timestamp = timestamp if timestamp else composite_state.get(composite)
    filename = 'himawari_{}_{}.tif'.format(composite, timestamp.strftime('%Y%m%d_%H%M'))
    object_name = '{}/{}/{}'.format(
        composite, timestamp.strftime('%Y/%m/%d'), filename
    )
    return object_name

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
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
def tile(composite, timestamp, z, x, y):
    """
    Tile request with ISO 8601 time format
    test url: http://localhost:5000/ash/tiles/2025-04-20T04:00:00/5/25/15.png
    """
    try:
        # Parse ISO 8601 time string
        request_time = datetime.datetime.fromisoformat(timestamp)
        return find_tile(composite, z, x, y, request_time)
    except ValueError:
        error_msg = {
            "error": "Invalid Time Format",
            "message": "Invalid time format. Please use ISO 8601 format (e.g., 2023-04-20T04:00:00)",
            "provided_time": timestamp
        }
        return jsonify(error_msg), 400

@app.route('/<composite>.tilejson')
def tilejson(composite):
    if composite not in available_composites:
        error_msg = {
            "error": "Not Found",
            "message": f"Composite {composite} not available",
            "available_composites": available_composites
        }
        return jsonify(error_msg), 404

    try:
        object_name = find_composite_object(composite)

        try:
            presigned_url = client.presigned_get_object(
                bucket_name='himawari',
                object_name=object_name,
                expires=datetime.timedelta(hours=24)
            )
            with Reader(presigned_url) as cog:
                return jsonify({
                    "bounds": cog.get_geographic_bounds(cog.tms.rasterio_geographic_crs),
                    "minzoom": cog.minzoom,
                    "maxzoom": cog.maxzoom,
                    "name": extract_composite_from_object_name(object_name),
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
    Handle MinIO events for object creation/update
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
                    app.logger.info(f"Updated state for {composite_name}: {timestamp}")

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
            timestamp = datetime.datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
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

        return jsonify({
            'message': 'Task status updated successfully'
        })

    except Exception as e:
        app.logger.error(f"Error updating task status: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
