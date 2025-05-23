import os
import dask
import satpy
import datetime
import time
import s3fs

from satpy import Scene
from pyresample import create_area_def

from upload import upload
from utils import logger, timing

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
    'true_color', 'night_microphysics', 'ir_clouds','ash'
]

# Mapping from our naming to satpy composite names
composite_mapping = {
    'true_color': 'true_color',
    'night_microphysics': 'night_microphysics',
    'ir_clouds': 'B13',
    'ash': 'ash'
}

def _replace_minute(time):
    minute = int(time.minute / 10) * 10
    return time.replace(minute=minute)

def _available_latest_time():
    utc = datetime.datetime.now(datetime.timezone.utc)
    time = _replace_minute(utc)
    return time - datetime.timedelta(minutes=20)

def check_files_available(target_time):
    """Check if 160 files are available for the given time"""
    try:
        fs = s3fs.S3FileSystem(anon=True)
        s3_path = 'noaa-himawari9/AHI-L1b-FLDK/{}'.format(target_time.strftime('%Y/%m/%d/%H%M'))

        files = fs.ls(s3_path)
        file_count = len(files)

        logger.info(f"Found {file_count} files for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        return file_count >= 160
    except Exception as e:
        logger.error(f"Error checking files for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC: {e}")
        return False

def ahi_s3_files(time=None, cache=False):
    if time is None:
        time = _available_latest_time()

    base_path = 's3://noaa-himawari9/AHI-L1b-FLDK/{}/*'.format(time.strftime('%Y/%m/%d/%H%M'))

    if cache:
        base_path = 'simplecache::' + base_path

    return [base_path]

@timing
def process_composite(composite_name, target_time):
    """Process a single composite for the given time"""
    try:
        logger.info(f"Processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

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
        name = 'himawari_{}_{}.tif'.format(composite_name, scn.start_time.strftime('%Y%m%d_%H%M'))
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

        object_name = '{}/{}/{}'.format(
            composite_name, scn.start_time.strftime('%Y/%m/%d'), name
        )

        upload('himawari', object_name, filename, composite_name)
        logger.info(f"Successfully processed and uploaded composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        return True
    except Exception as e:
        logger.error(f"Error processing composite '{composite_name}' for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC: {e}")
        return False

def main():
    """Main continuous processing loop"""
    logger.info("Starting Himawari continuous processing...")

    processed_times = set()  # Keep track of processed times in memory
    current_target_time = None

    while True:
        try:
            # Get the latest available time
            latest_time = _available_latest_time()

            # If we don't have a current target time, set it to the latest time
            if current_target_time is None:
                current_target_time = latest_time

            # If we've processed the current target time, move to the next 10-minute interval
            if current_target_time in processed_times:
                current_target_time = current_target_time + datetime.timedelta(minutes=10)

            # If the current target time is still in the future compared to latest available, wait
            if current_target_time > latest_time:
                logger.info(f"Target time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC is ahead of latest available time {latest_time.strftime('%Y-%m-%d %H:%M')} UTC, waiting...")
                time.sleep(60)
                continue

            logger.info(f"Checking data availability for time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")

            # Check if files are available (don't time this, it's just a quick check)
            if check_files_available(current_target_time):
                logger.info(f"Data complete for time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC, starting processing...")

                # Start timing for total processing
                total_start_time = time.time()

                # Process all composites for this time
                success_count = 0
                failed_composites = []
                composite_results = {}

                for composite_name in available_composites:
                    success, duration = process_composite(composite_name, current_target_time)
                    composite_results[composite_name] = duration

                    if success:
                        success_count += 1
                    else:
                        failed_composites.append(composite_name)

                total_end_time = time.time()
                total_duration = total_end_time - total_start_time
                total_composite_time = sum(composite_results.values())
                estimated_download_time = total_duration - total_composite_time

                if success_count == len(available_composites):
                    # Mark this time as processed
                    processed_times.add(current_target_time)

                    # Format timing information
                    def format_time(seconds):
                        if seconds < 60:
                            return f"{seconds:.2f}s"
                        else:
                            minutes = int(seconds // 60)
                            remaining_seconds = seconds % 60
                            return f"{minutes}m {remaining_seconds:.2f}s"

                    logger.info(f"All {success_count} composites processed successfully for time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")

                    # Log individual composite times
                    for composite_name, duration in composite_results.items():
                        logger.info(f"  {composite_name}: {format_time(duration)}")

                    logger.info(f"Total processing time: {format_time(total_duration)}, Estimated download time: {format_time(estimated_download_time)}")
                else:
                    logger.error(f"{success_count}/{len(available_composites)} composites succeeded for time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC. Failed: {failed_composites}. Will retry...")
            else:
                logger.info(f"Data not complete for time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC, waiting...")

            # Wait 1 minute before next check
            logger.info("Waiting 1 minute before next check...")
            time.sleep(60)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.info("Waiting 1 minute before retrying...")
            time.sleep(60)

if __name__ == '__main__':
    main()