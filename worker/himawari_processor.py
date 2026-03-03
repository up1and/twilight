import os
import gc
import functools

import dask
import numpy as np

from satpy import Scene
from pyresample import create_area_def

from dask.diagnostics import ProgressBar, ResourceProfiler
from dask.diagnostics.profile_visualize import visualize

from client import upload, check_object_exists
from utils import logger, timing


# Set cache directory based on OS
cache_dir = (
    os.path.join(os.environ["TEMP"], "satpy_cache")
    if os.name == "nt"
    else "/tmp/satpy_cache"
)


def memory_profiler(chunk_size="256mb", save_profile=True):
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
            time_str = target_time.strftime("%Y%m%d_%H%M")

            # Set memory limit for this operation
            with dask.config.set({"array.chunk-size": chunk_size}):
                # Initialize diagnostics
                resource_prof = ResourceProfiler(dt=0.25)  # Sample every 250ms
                progress = ProgressBar()

                with resource_prof, progress:
                    # Execute the original function
                    result = func(*args, **kwargs)

                # Log detailed resource usage
                try:
                    # Extract memory usage from resource profiler
                    memory_usage = [entry["memory"] for entry in resource_prof.results if "memory" in entry]
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
    "true_color", "ir_clouds", "ash", "night_microphysics"
]

# Mapping from our naming to satpy composite names
composite_mapping = {
    "true_color": "true_color",
    "night_microphysics": "night_microphysics",
    "ir_clouds": "B13",
    "ash": "ash"
}


def get_reader_kwargs(data_source, cache=True):
    """
    Get reader kwargs based on data source
    
    Args:
        data_source: "local" or "remote"
        cache: whether to use simplecache
    
    Returns:
        dict: reader_kwargs for satpy Scene
    """
    from config import endpoint, access_key, secret_key
    
    if data_source == "remote":
        # Use remote S3 configuration (anonymous access)
        reader_kwargs = {
            "storage_options": {
                "s3": {"anon": True}
            }
        }

    else:  # local
        # Use local minio configuration
        reader_kwargs = {
            "storage_options": {
                "s3": {
                    "key": access_key,
                    "secret": secret_key,
                    "client_kwargs": {
                        "endpoint_url": f"http://{endpoint}"
                    }
                }
            }
        }
    
    if cache:
        reader_kwargs["storage_options"]["simplecache"] = {
            "cache_storage": cache_dir,
            "cache_check": 600,
        }
    
    return reader_kwargs


def ahi_s3_files(time, data_source="remote", cache=True):
    """
    Get AHI data files based on data source preference
    
    Args:
        time: target datetime
        data_source: "local" or "remote"
        cache: whether to use simplecache
    
    Returns:
        list: file paths for satpy scene
    """
    if data_source == "remote":
        # Server has already checked data availability, use local first
        base_path = "s3://noaa-himawari9/AHI-L1b-FLDK/{}/*".format(time.strftime("%Y/%m/%d/%H%M"))
    else:
        base_path = "s3://raw/AHI-L1b-FLDK/{}/*".format(time.strftime("%Y/%m/%d/%H%M"))
    
    if cache:
        base_path = "simplecache::" + base_path
    
    return [base_path]

def get_custom_area(bbox, res_meters):
    """
    Generate an AreaDefinition based on lon/lat bounding box and target resolution.
    
    Args:
        bbox: [min_lon, min_lat, max_lon, max_lat]
        res_meters: Target resolution in meters (e.g., 500, 1000, 2000)
        
    Returns:
        AreaDefinition: A pyresample object for EPSG:4326 projection.
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    # Calculate degree-based resolution adjusted for latitude convergence
    deg_per_m = 1.0 / 111319.44
    center_lat = (min_lat + max_lat) / 2.0
    res_lat = res_meters * deg_per_m
    res_lon = res_lat / np.cos(np.radians(center_lat))

    # Calculate initial dimensions
    width = int(np.ceil((max_lon - min_lon) / res_lon))
    height = int(np.ceil((max_lat - min_lat) / res_lat))

    # Align to 256-pixel tiles (Optimal for Cloud Optimized GeoTIFF)
    tile_size = 256
    width = ((width + tile_size - 1) // tile_size) * tile_size
    height = ((height + tile_size - 1) // tile_size) * tile_size

    # Adjust extent to match the aligned grid exactly
    max_lon = min_lon + width * res_lon
    max_lat = min_lat + height * res_lat

    area_def = create_area_def(
        area_id="china_area",
        projection="EPSG:4326",
        area_extent=(min_lon, min_lat, max_lon, max_lat),
        width=width,
        height=height,
        units="degrees"
    )
    return area_def

@timing
@memory_profiler()
def process_composite(composite_name, target_time, data_source="remote"):
    """Process a single composite for the given time"""
    try:
        logger.info(f"Processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC from {data_source}")

        # Check if the file already exists in Minio
        name = "himawari_{}_{}.tif".format(composite_name, target_time.strftime("%Y%m%d_%H%M"))
        object_name = "{}/{}/{}".format(
            composite_name, target_time.strftime("%Y/%m/%d"), name
        )

        if check_object_exists("himawari", object_name):
            logger.info(f"Composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC already exists in Minio, skipping processing")
            return

        # Get the actual satpy composite name
        satpy_composite_name = composite_mapping.get(composite_name, composite_name)      
        files = ahi_s3_files(time=target_time, data_source=data_source, cache=True)
        reader_kwargs = get_reader_kwargs(data_source, cache=True)

        scn = Scene(filenames=files, reader="ahi_hsd", reader_kwargs=reader_kwargs)
        scn.load([satpy_composite_name])

        # Determine target resolution
        loaded_res = [
            scn[ds_id].attrs.get('resolution') 
            for ds_id in scn.keys() 
            if scn[ds_id].attrs.get('resolution')
        ]
        max_res = min(loaded_res)
        target_res = max(1000, max_res)

        # Native Resampling
        scn = scn.resample(resampler='native')

        gc.collect()

        china_bbox = [75, 0, 160, 55]  # lon: 75°-160°，lat 0°-55°
        china_area = get_custom_area(china_bbox, target_res)
        logger.info(f"Target Area: {china_area.width}x{china_area.height} at {target_res}m")

        # Resample with chunking for memory efficiency
        chunks = {"y": 2048, "x": 2048}
        scn_china = scn.resample(china_area, resampler="nearest", chunks=chunks)
        filename = os.path.join(cache_dir, name)

        scn_china.save_dataset(
            satpy_composite_name,
            filename=filename,
            driver="COG",
            tiled=True,
            blockxsize=512,
            blockysize=512,
            compress="deflate",
            predictor=2
        )

        upload("himawari", object_name, filename, composite_name)
        logger.info(f"Successfully processed and uploaded composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        del scn
        del scn_china
        gc.collect()

    except Exception as e:
        logger.error(f"Error processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC: {e}", exc_info=True)
        raise e
