from mercantile import tiles

bounds = (70.0, 0.0, 150.0, 55.0)  # (min_lon, min_lat, max_lon, max_lat)
min_zoom = 1
max_zoom = 10

all_tiles = []

for zoom in range(min_zoom, max_zoom + 1):
    tiles_at_zoom = list(tiles(*bounds, zooms=zoom))
    all_tiles.extend(tiles_at_zoom)

with open('tile_urls.txt', 'w', encoding='utf-8') as f:
    for tile in all_tiles:
        f.write(f"http://localhost:5000/tiles/{tile.z}/{tile.x}/{tile.y}.png\n")

print(f"已生成 {len(all_tiles)} 个瓦片（Zoom {min_zoom}-{max_zoom}），保存至 tile_urls.txt")