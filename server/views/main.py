"""
Main views for the application (non-API routes)
"""
import os
import sqlite3
import datetime

from flask import Blueprint, Response, request, jsonify, current_app
from rio_tiler.io import Reader
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rasterio.errors import RasterioIOError

from extensions import cache, client
from utils import parse_iso_timestamp, upper_case, extract_composite_from_object_name, extract_timestamp_from_object_name
from snapshot import find_composite_object

# Create blueprint
main = Blueprint('main', __name__)


def find_tile(composite, z, x, y, timestamp=None):
    """
    Common function to handle tile requests with or without time parameter
    """
    if composite not in current_app.config['AVAILABLE_COMPOSITES']:
        error_msg = {
            "error": "Not Found",
            "message": f"Composite {composite} not available",
            "available_composites": current_app.config['AVAILABLE_COMPOSITES']
        }
        return jsonify(error_msg), 404

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
        current_app.logger.warning(f"Tile {z}/{x}/{y} is outside data bounds")
        error_msg = {
            "error": "Tile Outside Bounds",
            "message": f"Tile {z}/{x}/{y} is outside data bounds",
            "tile": {"z": z, "x": x, "y": y}
        }
        return jsonify(error_msg), 404

    except RasterioIOError as e:
        current_app.logger.error(f"Rasterio IO error for tile {z}/{x}/{y}: {str(e)}", exc_info=True)
        error_msg = {
            "error": "Rasterio IO Error",
            "message": f"Error reading raster data: {str(e)}",
            "tile": {"z": z, "x": x, "y": y}
        }
        return jsonify(error_msg), 500


@main.route("/<composite>/tiles/<timestamp>/<int:z>/<int:x>/<int:y>.png")
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


@main.route('/<composite>.tilejson')
@cache.cached(timeout=3600)  # Cache for 1 hour
def tilejson(composite):
    if composite not in current_app.config['AVAILABLE_COMPOSITES']:
        error_msg = {
            "error": "Not Found",
            "message": f"Composite {composite} not available",
            "available_composites": current_app.config['AVAILABLE_COMPOSITES']
        }
        return jsonify(error_msg), 404

    timestamp = current_app.composite_state.get(composite)
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
        current_app.logger.error(f"Rasterio IO error for tilejson {composite}: {str(e)}", exc_info=True)
        error_msg = {
            "error": "Rasterio IO Error",
            "message": f"Error reading raster data: {str(e)}",
            "composite": composite
        }
        return jsonify(error_msg), 500


@main.route('/lands/<int:z>/<int:x>/<int:y>.pbf')
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

    mbtiles_path = os.path.join(os.path.dirname(__file__), '..', 'natural_earth.mbtiles')

    if not os.path.exists(mbtiles_path):
        return jsonify({
            'error': 'Not Found',
            'message': 'natural_earth.mbtiles file not found'
        }), 404

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


@main.route('/')
def index():
    """
    Provide basic server information and instructions for use
    """
    info = {
        "status": "running",
        "description": "Himawari Tile Server",
        "available_composites": current_app.config['AVAILABLE_COMPOSITES'],
        "usage": {
            "tiles": {
                "standard": "/{composite}/tiles/{time}/{z}/{x}/{y}.png (ISO 8601 time format)"
            },
            "tilejson": "/{composite}.tilejson",
            "latest_times": "/composites/latest"
        },
        "examples": {
            "standard_tile": f"/ir_clouds/tiles/2025-04-20T04:00:00/5/25/15.png",
            "tilejson": f"/ir_clouds.tilejson",
            "latest_times": "/composites/latest"
        }
    }
    return jsonify(info)


@main.route('/minio/events', methods=['GET', 'POST'])
def minio_event():
    """
    Handle MinIO events for object creation/update (legacy fallback)
    """
    if request.method == 'POST':
        event = request.get_json()
        object_key = event.get('Key', '')
        # Split bucket name and object name
        parts = object_key.split('/', 1)
        if len(parts) < 2:
            return jsonify({"error": "Invalid Key format"}), 400

        _, object_name = parts

        composite_name = extract_composite_from_object_name(object_name, current_app.config['AVAILABLE_COMPOSITES'])
        timestamp = extract_timestamp_from_object_name(object_name)
        if composite_name and timestamp:
            # Only update if the timestamp is newer than what we have
            current_timestamp = current_app.composite_state.get(composite_name)
            if current_timestamp is None or timestamp > current_timestamp:
                # Update composite_state with the new timestamp
                current_app.composite_state[composite_name] = timestamp
                current_app.logger.info(f"Updated state via MinIO event for {composite_name}: {timestamp}")

        return jsonify(event), 201

    else:
        # GET request - return service status and composite state
        result = {
            'live': datetime.datetime.now(datetime.timezone.utc),
        }
        return jsonify(result)


@main.route('/composites/latest', methods=['GET'])
def latest_composite_state():
    """
    Get the latest update time for all composites
    """
    return jsonify(current_app.composite_state)


@main.route('/snapshots/<path:object_name>')
def serve_snapshot(object_name):
    """Get snapshot file from MinIO by object name"""
    # Get object from MinIO snapshot bucket
    response = client.get_object('snapshot', object_name)
    
    # Determine content type based on file extension
    if object_name.endswith('.mp4'):
        content_type = 'video/mp4'
    elif object_name.endswith('.png'):
        content_type = 'image/png'
    else:
        content_type = 'application/octet-stream'
    
    # Return file data as response
    return Response(
        response.read(),
        mimetype=content_type,
        headers={
            'Content-Disposition': f'inline; filename="{os.path.basename(object_name)}"'
        }
    )
