"""
Utility functions
"""
import re
import datetime


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


def extract_timestamp_from_object_name(object_name):
    """
    Extract timestamp from object name
    Expected format: composite/YYYY/MM/DD/himawari_composite_YYYYMMDD_HHMM.tif
    """
    match = re.search(r'_(\d{8})_(\d{4})\.tif$', object_name)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        # Parse datetime and set UTC timezone
        dt = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
        return dt.replace(tzinfo=datetime.timezone.utc)
    return None


def extract_composite_from_object_name(object_name, available_composites):
    """
    Extract composite name from object name
    """
    # Try to extract from the filename
    for composite in available_composites:
        if f"himawari_{composite}_" in object_name:
            return composite

    return None


def default_json_handler(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def initialize_composite_state(client, available_composites):
    """
    Initialize composite_state with the latest objects from MinIO
    """
    # Dictionary to store the latest update time for each composite
    composite_state = {composite: None for composite in available_composites}

    # Get all objects from MinIO in one call
    objects = list(client.list_objects('himawari', recursive=True))
    # Group objects by composite
    composite_objects = {}
    for obj in objects:
        composite_name = extract_composite_from_object_name(obj.object_name, available_composites)
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

    return composite_state
