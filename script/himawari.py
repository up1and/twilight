import os
import dask
import satpy
import datetime

from satpy import Scene
from pyresample import create_area_def

from upload import upload

if os.name == 'nt':
    cache_dir = os.path.join(os.environ['TEMP'], 'satpy_cache')
else:  # macOS/Linux
    cache_dir = "/tmp/satpy_cache"

print('cache dir', cache_dir)

dask.config.set({'array.chunk-size': '32MiB'})
satpy.config.set(
    cache_dir=cache_dir,  # 缓存目录
    cache_size=1e9  # 缓存大小（1GB）
)

os.makedirs(cache_dir, exist_ok=True)

available_composites = [
    'true_color', 'day_cloud_phase_distinction', 'night_microphysics', 'fog',
    'airmass', 'ash', 'water_vapor', 'day_convection', 'natural_color'
]

def _replace_minute(time):
    minute = int(time.minute / 10) * 10
    return time.replace(minute=minute)

def _available_latest_time():
    utc = datetime.datetime.now(datetime.timezone.utc)
    time = _replace_minute(utc)
    return time - datetime.timedelta(minutes=20)

def ahi_s3_files(time=None, cache=False):
    if time is None:
        time = _available_latest_time()

    base_path = 's3://noaa-himawari9/AHI-L1b-FLDK/{}/*'.format(time.strftime('%Y/%m/%d/%H%M'))

    if cache:
        base_path = 'simplecache::' + base_path

    return [base_path]

def main():
    composite_name = 'true_color'
    test_time = datetime.datetime(2025, 4, 20, 4, 0)
    files = ahi_s3_files(time=test_time, cache=True)

    reader_kwargs = {
        'storage_options': {
            's3': {'anon': True},
            'simplecache': {
                'cache_storage': cache_dir,
                'cache_check': 600,
            }
        }
    }

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

    scn = Scene(filenames=files, reader='ahi_hsd', reader_kwargs=reader_kwargs)
    scn.load([composite_name])
    scn_china = scn.resample(china_area, resampler='bilinear', chunks=512)
    name = 'himawari_{}_{}.tif'.format(composite_name, scn.start_time.strftime('%Y%m%d_%H%M'))
    filename = os.path.join(cache_dir, name)
    scn_china.save_dataset(
        composite_name,
        filename=filename,
        driver='COG',
        tiled=True,
        blockxsize=256,
        blockysize=256,
        compress='deflate' 
    )

    print(filename)
    if composite_name in available_composites:
        prefix = composite_name
    else:
        prefix = 'bands'

    object_name = '{}/{}/{}'.format(
        prefix, scn.start_time.strftime('%Y/%m/%d'), name
    )

    upload('himawari', object_name, filename, composite_name)

if __name__ == '__main__':
    main()