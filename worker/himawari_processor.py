import os
import gc

import dask
import psutil
import numpy as np

from satpy import Scene
from pyresample import create_area_def
from contextlib import contextmanager

from dask.diagnostics import Profiler, ResourceProfiler
from dask.distributed import Client, LocalCluster

from client import upload, check_object_exists
from utils import logger, timing


# Set cache directory based on OS
cache_dir = (
    os.path.join(os.environ["TEMP"], "satpy_cache")
    if os.name == "nt"
    else "/tmp/satpy_cache"
)

def compute_worker_allocation(mem_per_worker=7.0, system_margin=4.0):
    """
    Dynamically calculates the optimal number of worker processes based on 
    real-time hardware availability (RAM and CPU).

    Args:
        mem_per_worker (float): Estimated RAM consumption per worker in GB.
        system_margin (float): RAM to keep free for OS and other tasks. Default is 4GB.

    Returns:
        int: The calculated number of workers, constrained between 1 and the CPU core count.
        float: The effective available memory in GB.
    """
    vm = psutil.virtual_memory()

    # Get available physical memory in GB
    if os.name == 'posix':  # Linux/Unix
        actual_used = vm.total - vm.free - getattr(vm, 'cached', 0) - getattr(vm, 'buffers', 0)
        available_mem = (vm.total - actual_used) / (1024**3)
    else:
        available_mem = vm.available / (1024**3)

    # Get the number of logical CPU cores
    try:
        logical_cores = len(os.sched_getaffinity(0))
    except AttributeError:
        logical_cores = psutil.cpu_count(logical=True) or 8

    # Calculate how many workers the available RAM can support
    effective_mem = max(0, available_mem - system_margin)
    dynamic_count = int(effective_mem // mem_per_worker)

    n_workers = max(1, min(dynamic_count, logical_cores))
    return n_workers, effective_mem

@contextmanager
def dask_scope(mem_per_worker=7.0, system_margin=4.0):
    """
    Dynamic resource management context: 
    Calculates the safe number of Dask threads based on real-time RAM availability.
    
    Args:
        mem_per_worker: Estimated peak RAM per parallel AHI task.
        system_margin: RAM to keep free for OS and other tasks.
    """
    n_workers, available_mem = compute_worker_allocation(mem_per_worker, system_margin)

    logger.info(f"Dask Scope Started: {n_workers} workers, RAM {available_mem:.1f} GB")

    settings = {
        "scheduler": "threads",
        "num_workers": n_workers
    }
    with Profiler() as prof, ResourceProfiler(dt=1) as rprof:
        with dask.config.set(settings):
            try:
                yield prof, rprof
            finally:
                gc.collect()

@contextmanager
def dask_scope_with_cluster(mem_per_worker=7.0, system_margin=4.0):
    """
    Context manager to handle Dask lifecycle.
    Ensures memory is fully released after each processing task.
    """
    # Constrain within [1, logical_cores] range
    n_workers, available_mem = compute_worker_allocation(mem_per_worker, system_margin)
    threads_per_worker = 1
    memory_limit = available_mem / n_workers

    # Initialize Cluster
    cluster = LocalCluster(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit=f"{memory_limit:.2f}GB",
        processes=True,
        dashboard_address=':8787'
    )
    
    # Global memory protection settings
    dask.config.set({
        "distributed.worker.memory.target": 0.7,
        "distributed.worker.memory.spill": 0.85,
        "distributed.worker.memory.pause": 0.90,
    })
    
    logger.info(f"Dask Cluster Started: {n_workers} workers, {threads_per_worker} threads, {memory_limit:.1f} GB/worker")
    
    with Profiler() as prof, ResourceProfiler(dt=1) as rprof:
        client = Client(cluster)
        try:
            yield prof, rprof
        finally:
            client.close()
            cluster.close()
            gc.collect()

# Mapping from our naming to satpy composite names
composite_mapping = {
    "true_color": "true_color_with_night_ir",
    "night_microphysics": "night_microphysics",
    "day_microphysics": "day_microphysics_ahi",
    "ir_clouds": "B13",
    "ash": "ash",
    "airmass": "airmass",
    "fog": "fog",
    "upper_vapor": "water_vapors1",
    "mid_vapor": "mid_vapor",
    "lower_vapor": "water_vapors2",
    "geo_color": "geo_color",
    "natural_color": "natural_color",
    "dust": "dust",
    "convection": "convection"
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
        area_id="area",
        projection="EPSG:4326",
        area_extent=(min_lon, min_lat, max_lon, max_lat),
        width=width,
        height=height,
        units="degrees"
    )
    return area_def

@timing
def process_composite(composite_name, target_time, data_source="remote", max_resolution=1000, bbox=None, resampler="nearest"):
    """Process a single composite for the given time"""
    if bbox is None:
        bbox = [75, 0, 160, 55] # lon: 75°-160°，lat 0°-55°

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
        target_res = max(max_resolution, max_res)

        # Native Resampling
        scn = scn.resample(resampler='native')

        area = get_custom_area(bbox, target_res)
        logger.info(f"Target Area: {area.width}x{area.height} at {target_res}m")

        # Resample with chunking for memory efficiency
        chunks = {"y": 1024, "x": 1024}
        scn_resampled = scn.resample(area, resampler=resampler, chunks=chunks)
        filename = os.path.join(cache_dir, name)

        scn_resampled.save_dataset(
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
        del scn_resampled

    except Exception as e:
        logger.error(f"Error processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC: {e}", exc_info=True)
        raise e
