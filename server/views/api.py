"""
API views for the application
"""
import datetime

from flask import Blueprint, request, jsonify, url_for, current_app

from auth import auth_required
from utils import parse_iso_timestamp
from snapshot import create_single_snapshot, create_series_snapshot

# Create blueprint
api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/auth/verify", methods=["POST"])
def verify_token():
    data = request.get_json()
    if not data or "token" not in data:
        return jsonify({"valid": False}), 400

    token = data["token"]
    is_valid = token == current_app.config["AUTH_KEY"]

    return jsonify({"valid": is_valid})


@api.route("/tasks", methods=["POST"])
@auth_required
def create_task():
    """Create a new processing task"""
    data = request.get_json()

    # Validate required fields
    if not data or "composite" not in data or "timestamp" not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Missing required fields: composite, timestamp"
        }), 400

    composite = data["composite"]
    if composite not in current_app.config["AVAILABLE_COMPOSITES"]:
        return jsonify({
            "error": "Bad Request",
            "message": f"Invalid composite. Available: {current_app.config['AVAILABLE_COMPOSITES']}"
        }), 400

    # Parse timestamp
    try:
        timestamp = parse_iso_timestamp(data["timestamp"])
    except ValueError:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid timestamp format. Use ISO 8601 format"
        }), 400

    priority = data.get("priority", "normal")
    if priority not in ["low", "normal", "high"]:
        priority = "normal"

    # Create task
    task = current_app.task_manager.create_task(composite, timestamp, priority)

    return jsonify({
        "task_id": task.task_id,
        "status": task.status,
        "created": task.created
    }), 201


@api.route("/tasks/<task_id>", methods=["GET"])
@auth_required
def get_task(task_id):
    """Get task details by ID"""
    task = current_app.task_manager.get_task(task_id)
    if not task:
        return jsonify({
            "error": "Not Found",
            "message": f"Task {task_id} not found"
        }), 404

    return jsonify(task.to_dict())


@api.route("/tasks", methods=["GET"])
@auth_required
def get_tasks():
    """Get tasks with optional filtering"""
    try:
        status = request.args.get("status")
        composite = request.args.get("composite")
        priority = request.args.get("priority")
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)  # Max 100 per page
    except ValueError:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid page or per_page parameter"
        }), 400

    offset = (page - 1) * per_page
    tasks, total = current_app.task_manager.get_tasks(status, composite, priority, per_page, offset)

    return jsonify({
        "tasks": [task.to_dict() for task in tasks],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    })


@api.route("/tasks/next", methods=["GET"])
@auth_required
def peek_next_task():
    """Peek next pending task for worker with optional filtering"""
    # Parse query parameters for filtering
    priorities = request.args.get("priority", "").split(",") if request.args.get("priority") else []
    composites = request.args.get("composite", "").split(",") if request.args.get("composite") else []
    
    # Filter out empty strings
    priorities = [p.strip() for p in priorities if p.strip()]
    composites = [c.strip() for c in composites if c.strip()]
    
    task = current_app.task_manager.peek_next_task(priorities=priorities, composites=composites)
    if not task:
        return jsonify({
            "message": "No pending tasks"
        }), 204  # No Content

    return jsonify({
        "task_id": task.task_id,
        "composite": task.composite,
        "timestamp": task.timestamp,
        "priority": task.priority
    })


@api.route("/tasks/<task_id>/claim", methods=["PUT"])
@auth_required
def claim_task(task_id):
    """Claim a specific task for processing"""
    data = request.get_json()
    if not data or "worker_id" not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Missing required field: worker_id"
        }), 400

    worker_id = data["worker_id"]
    
    # Claim the task
    task = current_app.task_manager.claim_task(task_id, worker_id)
    if not task:
        return jsonify({
            "error": "Not Found",
            "message": f"Task {task_id} not found or already claimed"
        }), 404

    return jsonify({
        "task_id": task.task_id,
        "composite": task.composite,
        "timestamp": task.timestamp,
        "status": task.status,
        "worker_id": task.worker_id
    })


@api.route("/tasks/<task_id>/status", methods=["PUT"])
@auth_required
def update_task_status(task_id):
    """Update task status"""
    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Missing required field: status"
        }), 400

    status = data["status"]
    if status not in ["pending", "processing", "completed", "failed"]:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid status. Must be: pending, processing, completed, failed"
        }), 400
    
    # Get task details before updating status
    task = current_app.task_manager.get_task(task_id)
    if not task:
        return jsonify({
            "error": "Not Found",
            "message": f"Task {task_id} not found"
        }), 404

    message = data.get("message")
    success = current_app.task_manager.update_task_status(task_id, status, message)
    if not success:
        return jsonify({
            "error": "Not Found",
            "message": f"Task {task_id} not found"
        }), 404
    
    # Update composite_state when task is completed
    if status == "completed":
        composite_name = task.composite
        timestamp = task.timestamp

        # Only update if this timestamp is newer than what we have
        current_timestamp = current_app.composite_state.get(composite_name)
        if current_timestamp is None or timestamp > current_timestamp:
            current_app.composite_state.update(composite_name, timestamp)
            current_app.logger.info(f"Updated composite state via task completion: {composite_name} -> {timestamp}")

    return jsonify({
        "message": "Task status updated successfully"
    })


@api.route("/tasks/<task_id>/profile", methods=["POST"])
@auth_required
def create_task_profile(task_id):
    """Receive profiler data from worker"""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Bad Request", "message": "Missing request body"}), 400

    task = current_app.task_manager.get_task(task_id)
    if not task:
        return jsonify(
            {"error": "Not Found", "message": f"Task {task_id} not found"}
        ), 404

    tasks = data.get("tasks", [])
    resources = data.get("resources", [])

    current_app.task_manager.save_profile(task_id, tasks, resources)

    return jsonify({"message": "Profile saved"}), 201


@api.route("/tasks/<task_id>/profile", methods=["GET"])
@auth_required
def get_task_profile(task_id):
    """Get profiler data for a task"""
    profile = current_app.task_manager.get_profile(task_id)

    if not profile:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Profile data for task {task_id} not found",
            }
        ), 404

    return jsonify(
        {
            "task_id": task_id,
            "tasks": profile["tasks"],
            "resources": profile["resources"],
        }
    )


@api.route("/syncs", methods=["POST", "PUT"])
@auth_required
def manage_sync():
    """Create or update sync record for a timestamp"""
    data = request.get_json()
    
    # Validate required fields
    if not data or "timestamp" not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Missing required field: timestamp"
        }), 400
        
    # Parse timestamp
    try:
        timestamp = parse_iso_timestamp(data["timestamp"])
    except ValueError:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid timestamp format. Use ISO 8601 format"
        }), 400
    
    # Extract source (default to himawari)
    source = data.get("source", "himawari")
    
    # Handle POST request (create pending)
    if request.method == "POST":
        # Create pending sync record
        current_app.sync_manager.create_sync(source, timestamp)
        
        return jsonify({
            "message": f"{source.capitalize()} sync created successfully",
            "timestamp": timestamp.isoformat(),
            "source": source,
            "status": "pending"
        }), 201
    
    # Handle PUT request (update progress)
    else:  # PUT
        # Extract optional fields
        status = data.get("status")
        files = data.get("files")
        size = data.get("size")
        
        # Validate that at least one field is provided
        if status is None and files is None and size is None:
            return jsonify({
                "error": "Bad Request",
                "message": "At least one of status, files, or size must be provided"
            }), 400
        
        # Validate status if provided
        if status is not None:
            valid_statuses = ["pending", "running", "completed", "failed"]
            if status not in valid_statuses:
                return jsonify({
                    "error": "Bad Request",
                    "message": f"Invalid status. Valid values: {valid_statuses}"
                }), 400
            
        # Update progress with partial data
        current_app.sync_manager.update_progress(source, timestamp, status, files, size)
        
        # Build response message
        updated_fields = []
        if status is not None:
            updated_fields.append(f'status={status}')
        if files is not None:
            updated_fields.append(f'files={files}')
        if size is not None:
            updated_fields.append(f'size={size}')
        
        return jsonify({
            "message": f"{source.capitalize()} sync updated successfully ({', '.join(updated_fields)})",
            "timestamp": timestamp.isoformat(),
            "source": source
        })


@api.route("/syncs/<timestamp>", methods=["GET"])
@auth_required
def get_sync(timestamp):
    """Get sync progress for a specific timestamp"""
    # Parse timestamp
    try:
        parsed_time = parse_iso_timestamp(timestamp)
    except ValueError:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid timestamp format. Use ISO 8601 format"
        }), 400
    
    source = request.args.get("source", "himawari")
    sync_data = current_app.sync_manager.get_sync(source, parsed_time)
    if not sync_data:
        return jsonify({
            "error": "Not Found",
            "message": f"No {source} sync found for {timestamp}"
        }), 404
        
    return jsonify(sync_data)


@api.route("/syncs", methods=["GET"])
@auth_required
def get_syncs():
    """Get all sync records with pagination"""
    try:
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)  # Max 100 per page
    except ValueError:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid page or per_page parameter"
        }), 400

    source = request.args.get("source")
    offset = (page - 1) * per_page
    syncs, total = current_app.sync_manager.get_syncs(source, per_page, offset)
    
    return jsonify({
        "syncs": syncs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0
    })


composite_availability = {
    "day_microphysics": "day",
    "night_microphysics": "night",
    "true_color": "day",
    "fog": "night",
    "convection": "day",
}


@api.route("/composites", methods=["GET"])
def composites():
    """Get all composites with latest timestamp and availability."""
    state = current_app.composite_state.get()
    result = {}
    for composite, timestamp in state.items():
        result[composite] = {
            "timestamp": timestamp,
            "availability": composite_availability.get(composite, "all"),
        }
    return jsonify(result)


@api.route("/snapshots", methods=["POST"])
def create_snapshot():
    """Create a snapshot image or video with geographic bounds and coastlines"""
    from extensions import client
    
    data = request.get_json()

    # Validate required fields
    required_fields = ["bbox", "timestamp", "composite"]
    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": "Bad Request",
                "message": f"Missing required field: {field}"
            }), 400

    bbox = data["bbox"]
    timestamp = data["timestamp"]
    composite = data["composite"]
    timedelta_minutes = data.get("timedelta")  # Optional time delta in minutes

    # Validate bbox format
    if not isinstance(bbox, list) or len(bbox) != 4:
        return jsonify({
            "error": "Bad Request",
            "message": "bbox must be an array of 4 numbers [min_lng, min_lat, max_lng, max_lat]"
        }), 400

    # Validate composite
    if composite not in current_app.config["AVAILABLE_COMPOSITES"]:
        return jsonify({
            "error": "Bad Request",
            "message": f"Invalid composite. Available: {current_app.config['AVAILABLE_COMPOSITES']}"
        }), 400

    # Parse timestamps
    try:
        start_time = parse_iso_timestamp(timestamp)
    except ValueError:
        return jsonify({
            "error": "Bad Request",
            "message": "Invalid timestamp format. Use ISO 8601 format"
        }), 400

    if timedelta_minutes:
        # Validate timedelta
        if not isinstance(timedelta_minutes, (int, float)) or timedelta_minutes <= 0:
            return jsonify({
                "error": "Bad Request",
                "message": "timedelta must be a positive number (minutes)"
            }), 400

        # Validate time range (max 24 hours = 1440 minutes)
        if timedelta_minutes > 1440:
            return jsonify({
                "error": "Bad Request",
                "message": "Time range cannot exceed 24 hours (1440 minutes)"
            }), 400

        # Calculate end time
        end_time = start_time + datetime.timedelta(minutes=timedelta_minutes)

    # Create video from time range
    if timedelta_minutes:
        result = create_series_snapshot(client, composite, start_time, end_time, bbox, current_app.task_manager)
    else:
        # Create single snapshot
        result = create_single_snapshot(client, composite, start_time, bbox, current_app.task_manager)

    # Only add download_url if object_name exists (successful completion)
    if "object_name" in result:
        object_name = result.pop("object_name")
        result["download_url"] = f"/snapshots/{object_name}"
    if result["status"] == "pending":
        return jsonify(result), 202
    else:
        return jsonify(result), 201
