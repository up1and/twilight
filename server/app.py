import os
import shapefile

from flask import Flask, jsonify

app = Flask(__name__)
root = os.path.abspath(os.path.dirname(__file__))
filename = os.path.join(root, 'shapes', 'coastline.shp')

def shapefile_to_geojson(filename):
    sf = shapefile.Reader(filename)
    fields = sf.fields[1:]
    field_names = [field[0] for field in fields]
    buffer = []
    for sr in sf.shapeRecords():
        atr = dict(zip(field_names, sr.record))
        geom = sr.shape.__geo_interface__
        buffer.append(dict(type="Feature", \
            geometry=geom, properties=atr))
    
    return {
        'type': 'FeatureCollection',
        'features': buffer
    }

geometries = shapefile_to_geojson(filename)

@app.route('/natural-earth')
def natural_earth():
    return geometries


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)