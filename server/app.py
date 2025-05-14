import os
import datetime

from flask import Flask, Response, request, jsonify, abort
from rio_tiler.io import Reader
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds

from minio import Minio
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
    name = composite
    folder = composite

    if composite == 'ir_clouds':
        name = 'B13'
        folder = 'bands'

    if time:
        filename = 'himawari_{}_{}.tif'.format(name, time.strftime('%Y%m%d_%H%M'))
        object_name = '{}/{}/{}'.format(
            folder, time.strftime('%Y/%m/%d'), filename
        )
        return object_name
    else:
        objects = client.list_objects('himawari', prefix=folder, recursive=True)
        for object in objects:
            if composite == 'ir_clouds' and name in object.object_name:
                return object.object_name
            return object.object_name

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route("/<composite>/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(composite, z, x, y):
    """
    test url http://localhost:5000/ash/tiles/5/25/15.png
    """
    if composite not in available_composites:
        abort(404, description='Composite {composite} not available. Options: {available_composites}'.format(
            composite=composite, available_composites=available_composites))
        
    time = datetime.datetime(2025, 4, 20, 4, 0)
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
        return "Tile outside bounds", 404
    except Exception as e:
        app.logger.error(f"Error generating tile {z}/{x}/{y}: {str(e)}", exc_info=True)
        return "Internal server error", 500
    
@app.route('/<composite>/tilejson.json')
def tilejson(composite):
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
                "tiles": [f"{request.host_url.rstrip('/')}/{composite}/tiles/{'{z}'}/{'{x}'}/{'{y}'}.png"],
            })
    except Exception as e:
        app.logger.error(str(e), exc_info=True)
        return "Internal server error", 500


@app.route('/')
def index():
    return Response("Tile server is running. Try /tiles/{z}/{x}/{y}.png", mimetype='text/plain')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
