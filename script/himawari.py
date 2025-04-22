import os
import dask

from satpy import Scene, find_files_and_readers
from pyresample import create_area_def

dask.config.set({'array.chunk-size': '32MiB'})

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def main():
    rgbname = 'true_color'
    input = os.path.join(root, 'script', 'hsd')
    files = find_files_and_readers(base_dir=input)

    china_bbox = [70, 0, 150, 55]  # 东经70°-150°，纬度0°-55°

    lon_span = china_bbox[2] - china_bbox[0]
    lat_span = china_bbox[3] - china_bbox[1]

    pixel_resolution = 0.02
    width = int(lon_span / pixel_resolution)  # 80° / 0.02° = 4000
    height = int(lat_span / pixel_resolution) # 55° / 0.02° = 2750

    china_area = create_area_def(
        area_id='china',  # 区域唯一标识符
        projection='EPSG:4326',  # WGS84经纬度投影
        width=width,
        height=height,
        area_extent=china_bbox,  # [min_lon, min_lat, max_lon, max_lat]
    )

    scn = Scene(filenames=files, reader='ahi_hsd')
    scn.load([rgbname])
    scn_china = scn.resample(china_area, resampler='bilinear', chunks=512)
    filename = os.path.join(root, 'script', f'himawari_ahi_{rgbname}_{scn.start_time.strftime('%Y%m%d%H%M')}.tif')
    scn_china.save_dataset(
        rgbname,
        filename=filename,
        driver='COG',
        tiled=True,
        blockxsize=256,
        blockysize=256,
        compress='deflate' 
    )

    print(filename)

if __name__ == '__main__':
    main()