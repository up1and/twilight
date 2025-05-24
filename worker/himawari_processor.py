import os

from satpy import Scene
from pyresample import create_area_def

from client import upload, check_object_exists
from utils import logger, timing


if os.name == 'nt':
    cache_dir = os.path.join(os.environ['TEMP'], 'satpy_cache')
else:  # macOS/Linux
    cache_dir = "/tmp/satpy_cache"

available_composites = [
    'true_color', 'ir_clouds', 'ash', 'night_microphysics'
]

# Mapping from our naming to satpy composite names
composite_mapping = {
    'true_color': 'true_color',
    'night_microphysics': 'night_microphysics',
    'ir_clouds': 'B13',
    'ash': 'ash'
}


def ahi_s3_files(time, cache=False):
    base_path = 's3://noaa-himawari9/AHI-L1b-FLDK/{}/*'.format(time.strftime('%Y/%m/%d/%H%M'))

    if cache:
        base_path = 'simplecache::' + base_path

    return [base_path]


@timing
def process_composite(composite_name, target_time):
    """Process a single composite for the given time"""
    try:
        logger.info(f"Processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        # Check if the file already exists in Minio
        name = 'himawari_{}_{}.tif'.format(composite_name, target_time.strftime('%Y%m%d_%H%M'))
        object_name = '{}/{}/{}'.format(
            composite_name, target_time.strftime('%Y/%m/%d'), name
        )

        if check_object_exists('himawari', object_name):
            logger.info(f"Composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC already exists in Minio, skipping processing")
            return True

        # Get the actual satpy composite name
        satpy_composite_name = composite_mapping.get(composite_name, composite_name)

        files = ahi_s3_files(time=target_time, cache=True)

        reader_kwargs = {
            'storage_options': {
                's3': {'anon': True},
                'simplecache': {
                    'cache_storage': cache_dir,
                    'cache_check': 600,
                }
            }
        }

        china_bbox = [75, 0, 160, 55]  # 东经75°-160°，纬度0°-55°

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
        scn.load([satpy_composite_name])

        scn_china = scn.resample(china_area, resampler='bilinear', chunks=512)
        filename = os.path.join(cache_dir, name)

        scn_china.save_dataset(
            satpy_composite_name,
            filename=filename,
            driver='COG',
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress='deflate'
        )

        upload('himawari', object_name, filename, composite_name)
        logger.info(f"Successfully processed and uploaded composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        return True
    except Exception as e:
        logger.error(f"Error processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC: {e}", exc_info=True)
        return False
