"""
Utility functions
"""
import re
import datetime


def upper_case(name):
    """
    Format composite name for display (e.g., "day_convection" to "Day Convection")
    """
    segments = name.split("_")
    formatted_segments = []
    
    for segment in segments:
        if len(segment) <= 2:
            formatted_segments.append(segment.upper())
        else:
            formatted_segments.append(segment[0].upper() + segment[1:].lower())
    
    return " ".join(formatted_segments)


def format_to_standard_iso(url_timestamp):
    """
    Converts a URL-friendly timestamp (YYYY-MM-DDTHH-mm-ssZ) 
    back to the standard ISO 8601 format (YYYY-MM-DDTHH:mm:ssZ)
    """
    date_part, time_part = url_timestamp.split("T")
    time_part = time_part.replace("-", ":")
    return f"{date_part}T{time_part}"


def parse_iso_timestamp(timestamp_str):
    """
    Parse an ISO 8601 timestamp string into a timezone-aware datetime object.
    """
    # Handle timezone-aware timestamps
    if timestamp_str.endswith("Z"):
        timestamp_str = timestamp_str.replace("Z", "+00:00")
    timestamp = datetime.datetime.fromisoformat(timestamp_str)
    # Ensure timezone-aware datetime
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
    
    return timestamp


def extract_timestamp_from_object_name(object_name):
    """
    Extract timestamp from object name
    Expected format: composite/YYYY/MM/DD/himawari_composite_YYYYMMDD_HHMM.tif
    """
    match = re.search(r"_(\d{8})_(\d{4})\.tif$", object_name)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        # Parse datetime and set UTC timezone
        dt = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
        return dt.replace(tzinfo=datetime.timezone.utc)
    return None


def default_json_handler(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def delete_minio_objects(client, bucket, path):
    """Delete objects in a MinIO bucket.
    
    If path contains a '.', it is treated as a specific object key.
    Otherwise, it is treated as a prefix for recursive deletion.
    """
    errors = []
    try:
        # Check if it's a specific file (contains a dot)
        if "." in path.split("/")[-1]:
            # Single file deletion
            try:
                client.remove_object(bucket, path)
            except Exception as e:
                errors.append(str(e))
        else:
            # Prefix-based recursive deletion
            objects = client.list_objects(bucket, prefix=path, recursive=True)
            obj_names = [obj.object_name for obj in objects]
            if obj_names:
                deletes = client.remove_objects(bucket, obj_names)
                for error in deletes:
                    errors.append(str(error))

    except Exception as e:
        errors.append(str(e))

    return errors


def initialize_composite_state(client, available_composites):
    """
    Initialize composite state by finding the latest available timestamp for each composite.
    Searches for the most recent composite images in MinIO storage.
    """
    composite_state = {composite: None for composite in available_composites}

    try:
        # Search the entire dataset for each composite to find the latest
        for composite in available_composites:
            latest_timestamp = None
            objects = client.list_objects("himawari", prefix=f"{composite}/", recursive=True)
            
            for obj in objects:
                timestamp = extract_timestamp_from_object_name(obj.object_name)
                if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                    latest_timestamp = timestamp
            
            composite_state[composite] = latest_timestamp

    except Exception as e:
        print(f"Warning: Failed to initialize composite state from MinIO: {e}")

    return composite_state