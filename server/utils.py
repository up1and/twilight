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


def initialize_composite_state(client, available_composites):
    """
    Initialize composite state by finding the latest available timestamp for each composite.
    Searches for the most recent composite images in MinIO storage, starting with the last 7 days
    and falling back to the entire dataset if no recent objects are found.
    """
    # Dictionary to store the latest update time for each composite
    composite_state = {composite: None for composite in available_composites}
    current_date = datetime.datetime.now(datetime.timezone.utc)

    for composite in available_composites:
        latest_timestamp = None

        try:
            # Get objects from MinIO
            max_keys = 1000
            search_date = current_date - datetime.timedelta(days=7)
            date_prefix = search_date.strftime("%Y/%m/%d")
            objects = client.list_objects("himawari", prefix=f"{composite}/{date_prefix}/", recursive=True)

            # If no objects found in the last 7 days, search the entire dataset
            if not list(objects):
                objects = client.list_objects("himawari", prefix=f"{composite}/", recursive=True)
            
            for i, obj in enumerate(objects):
                if i >= max_keys:
                    break

                timestamp = extract_timestamp_from_object_name(obj.object_name)
                if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                    latest_timestamp = timestamp

                if latest_timestamp:
                    composite_state[composite] = latest_timestamp

        except Exception as e:
            print(f"Warning: Failed to initialize composite state from MinIO: {e}")

    return composite_state