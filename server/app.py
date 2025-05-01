import os
from flask import Flask, Response, request, jsonify
from rio_tiler.io import Reader
from rio_tiler.errors import TileOutsideBounds
from io import BytesIO

# 配置
tiff_path = os.path.join(os.path.dirname(__file__), 'true_color.tif')
TILE_SIZE = 256

app = Flask(__name__)

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    try:
        with Reader(tiff_path) as cog:
            img = cog.tile(x, y, z, tilesize=256)
            content = img.render()
            return Response(content, mimetype="image/png")
    
    except TileOutsideBounds:
        app.logger.warning(f"Tile {z}/{x}/{y} is outside data bounds")
        return "Tile outside bounds", 404
    except Exception as e:
        app.logger.error(f"Error generating tile {z}/{x}/{y}: {str(e)}", exc_info=True)
        return "Internal server error", 500
    
@app.route('/tilejson.json')
def tilejson():
    try:
        with Reader(tiff_path) as cog:
            return jsonify({
                "bounds": cog.get_geographic_bounds(cog.tms.rasterio_geographic_crs),
                "minzoom": cog.minzoom,
                "maxzoom": cog.maxzoom,
                "name": os.path.basename(tiff_path),
                "tiles": [f"{request.host_url.rstrip('/')}/{'{z}'}/{'{x}'}/{'{y}'}.png"],
            })
    except Exception as e:
        app.logger.error(str(e), exc_info=True)
        return "Internal server error", 500


@app.route('/')
def index():
    return Response("Tile server is running. Try /tiles/{z}/{x}/{y}.png", mimetype='text/plain')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
