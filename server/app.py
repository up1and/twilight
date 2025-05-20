import datetime
import re

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
    'ir_clouds', 'true_color', 'day_cloud_phase_distinction', 'night_microphysics', 'fog',
    'airmass', 'ash', 'water_vapor', 'day_convection', 'natural_color'
]

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
                    "name": presigned_url,
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
