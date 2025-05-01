import os

from rio_tiler.io import Reader
from rio_tiler.models import ImageData, PointData

tile_x = 900
tile_y = 510
tile_zoom = 10


cog_path = os.path.join(os.path.dirname(__file__), 'true_color.tif')

with Reader(cog_path) as dst:
    # Read data for a slippy map tile
    img = dst.tile(tile_x, tile_y, tile_zoom, tilesize=256)
    assert isinstance(img, ImageData)  # Image methods return data as rio_tiler.models.ImageData object

    stats = dst.statistics()

    print(stats)

    # print(img.data.shape)
    # print('mask shape', img.mask.shape)

    # # Read the entire data
    # img = dst.read()
    # print(img.data.shape)

    # # Read part of a data for a given bbox (we use `max_size=1024` to limit the data transfer and read lower resolution data)
    # img = dst.part([-61.281, 15.539, -61.279, 15.541], max_size=1024)
    # print(img.data.shape)

    # # Get a preview (size is maxed out to 1024 by default to limit the data transfer and read lower resolution data)
    # img = dst.preview()
    # print(img.data.shape)

    buff = img.render()

    with open("my.png", "wb") as f:
        f.write(buff)
