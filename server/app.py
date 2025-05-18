import datetime

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

def find_composite_object(composite, time=None):
    if time:
        filename = 'himawari_{}_{}.tif'.format(composite, time.strftime('%Y%m%d_%H%M'))
        object_name = '{}/{}/{}'.format(
            composite, time.strftime('%Y/%m/%d'), filename
        )
        return object_name
    else:
        objects = client.list_objects('himawari', prefix=composite, recursive=True)
        object = list(objects)[-1]
        return object.object_name

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

def find_tile(composite, z, x, y, time=None):
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

    # Use provided time or default
    if time is None:
        time = datetime.datetime(2025, 4, 20, 4, 0)

    try:
        object_name = find_composite_object(composite, time)

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
        app.logger.error(f"S3 error for {composite} at time {time}: {str(e)}", exc_info=True)
        error_msg = {
            "error": "S3 Error",
            "message": f"Error accessing object storage: {str(e)}",
            "composite": composite,
            "time": time.isoformat() if time else None
        }
        return jsonify(error_msg), 500

@app.route("/<composite>/tiles/<time>/<int:z>/<int:x>/<int:y>.png")
def tile(composite, time, z, x, y):
    """
    Tile request with ISO 8601 time format
    test url: http://localhost:5000/ash/tiles/2025-04-20T04:00:00/5/25/15.png
    """
    try:
        # Parse ISO 8601 time string
        request_time = datetime.datetime.fromisoformat(time)
        return find_tile(composite, z, x, y, request_time)
    except ValueError:
        error_msg = {
            "error": "Invalid Time Format",
            "message": "Invalid time format. Please use ISO 8601 format (e.g., 2023-04-20T04:00:00)",
            "provided_time": time
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
            "tilejson": "/{composite}.tilejson"
        },
        "examples": {
            "standard_tile": f"/{available_composites[0]}/tiles/2025-04-20T04:00:00/5/25/15.png",
            "tilejson": f"/{available_composites[0]}.tilejson"
        }
    }
    return jsonify(info)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
