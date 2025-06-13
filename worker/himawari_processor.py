import os
import functools

from satpy import Scene
from pyresample import create_area_def

import dask
from dask.diagnostics import ProgressBar, ResourceProfiler
from dask.diagnostics.profile_visualize import visualize

from client import upload, check_object_exists
from utils import logger, timing


# Set cache directory based on OS
cache_dir = (
    os.path.join(os.environ['TEMP'], 'satpy_cache')
    if os.name == 'nt'
    else "/tmp/satpy_cache"
)


def memory_profiler(chunk_size='256mb', save_profile=True):
    """
    Decorator for memory profiling with Dask diagnostics

    Args:
        chunk_size: Dask chunk size for the operation
        save_profile: Whether to save HTML profile report
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract function name and args for profile naming
            func_name = func.__name__

            # Try to extract composite_name and target_time from args for naming
            composite_name, target_time, *_ = args
            time_str = target_time.strftime('%Y%m%d_%H%M')

            # Set memory limit for this operation
            with dask.config.set({'array.chunk-size': chunk_size}):
                # Initialize diagnostics
                resource_prof = ResourceProfiler(dt=0.25)  # Sample every 250ms
                progress = ProgressBar()

                with resource_prof, progress:
                    # Execute the original function
                    result = func(*args, **kwargs)

                # Log detailed resource usage
                try:
                    # Extract memory usage from resource profiler
                    memory_usage = [entry['memory'] for entry in resource_prof.results if 'memory' in entry]
                    peak_memory = max(memory_usage) / 1e9 if memory_usage else 0
                    logger.info(f"[{func_name}] Peak memory usage: {peak_memory:.2f} GB")
                except Exception as e:
                    logger.info(f"[{func_name}] Memory profiling completed (details unavailable: {e})")

                # Generate resource profile visualization (optional)
                if save_profile:
                    try:
                        profile_file = os.path.join(cache_dir, f"dask_profile_{func_name}_{composite_name}_{time_str}.html")
                        visualize([resource_prof], filename=profile_file, show=False)
                        logger.info(f"[{func_name}] Resource profile saved to: {profile_file}")
                    except Exception as e:
                        logger.warning(f"[{func_name}] Could not save resource profile: {e}")

                return result
        return wrapper
    return decorator


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
@memory_profiler()
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

        china_bbox = [75, 0, 160, 55]  # lon: 75°-160°，lat 0°-55°

        lon_span = china_bbox[2] - china_bbox[0]
        lat_span = china_bbox[3] - china_bbox[1]

        pixel_resolution = 0.02
        width = int(lon_span / pixel_resolution)  # 80° / 0.02° = 4000
        height = int(lat_span / pixel_resolution) # 55° / 0.02° = 2750

        china_area = create_area_def(
            area_id='china',
            projection='EPSG:4326',
            width=width,
            height=height,
            area_extent=china_bbox,  # [min_lon, min_lat, max_lon, max_lat]
        )

        scn = Scene(filenames=files, reader='ahi_hsd', reader_kwargs=reader_kwargs)
        scn.load([satpy_composite_name])

        dims = len(scn[satpy_composite_name].data.shape)
        chunks = (512, 512) if dims == 2 else ('auto', 512, 512)

        # Resample with chunking for memory efficiency
        scn_china = scn.resample(china_area, resampler='bilinear', chunks=chunks)
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
