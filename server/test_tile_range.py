from mercantile import tiles

bounds = (70.0, 0.0, 150.0, 55.0)
zoom = 10

# 计算覆盖该范围的所有瓦片
valid_tiles = list(tiles(*bounds, zooms=[zoom]))
print(f'Zoom {zoom} 的有效瓦片范围：')
for tile in valid_tiles:
    print(f'http://localhost:5000/tiles/{tile.z}/{tile.x}/{tile.y}.png')