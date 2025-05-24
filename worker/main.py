import datetime
import time
import s3fs
import argparse
import threading
import requests
import socket

from himawari_processor import available_composites
from task_manager import TaskManager
from utils import logger

def get_local_ip():
    """Get local IP address"""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def generate_worker_id():
    """Generate worker ID from hostname and IP"""
    hostname = socket.gethostname()
    ip = get_local_ip()
    return f"{hostname}_{ip}"

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

def task_generator_thread(server_url):
    """Task generator thread that monitors data availability and creates tasks"""
    logger.info("Starting Himawari task generator thread...")

    current_target_time = None

    while True:
        try:
            # Get the latest available time
            latest_time = _available_latest_time()

            # If we don't have a current target time, set it to the latest time
            if current_target_time is None:
                current_target_time = latest_time

            # If the current target time is still in the future compared to latest available, wait
            if current_target_time > latest_time:
                time.sleep(60)
                continue

            # Check if files are available
            if check_files_available(current_target_time):
                for composite_name in available_composites:
                    try:
                        # Create task on server (server will handle deduplication)
                        response = requests.post(
                            f"{server_url}/api/tasks",
                            json={
                                'composite': composite_name,
                                'timestamp': current_target_time.isoformat(),
                                'priority': 'normal'
                            },
                            timeout=10
                        )
                        if response.status_code == 201:
                            task_data = response.json()
                            task_id = task_data['task_id']
                            logger.info(f"Created task {task_id} for {composite_name} at {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")
                        else:
                            logger.error(f"Failed to create task for {composite_name}: {response.status_code} {response.text}")
                    except Exception as e:
                        logger.error(f"Error creating task for {composite_name}: {e}")

                # Move to next 10-minute interval
                current_target_time = current_target_time + datetime.timedelta(minutes=10)
            else:
                logger.info(f"Data not complete for time {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC, waiting...")

            # Wait 1 minute before next check
            logger.info("Waiting 1 minute before next check...")
            time.sleep(60)

        except KeyboardInterrupt:
            logger.info("Task generator received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in task generator: {e}")
            logger.info("Waiting 1 minute before retrying...")
            time.sleep(60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Himawari satellite data processing')
    parser.add_argument('--mode', choices=['hybrid', 'worker'], default='hybrid',
                        help='Processing mode: task (server-driven) or monitor (continuous)')
    parser.add_argument('--server-url', default='http://127.0.0.1:5000',
                        help='Task server URL')
    parser.add_argument('--worker-id', help='Worker ID (auto-generated if not provided)')
    parser.add_argument('--poll-interval', type=int, default=5,
                        help='Task polling interval in seconds')

    args = parser.parse_args()

    # Generate worker ID if not provided
    worker_id = args.worker_id or generate_worker_id()

    if args.mode == 'monitor':
        # Start task generator thread
        generator_thread = threading.Thread(
            target=task_generator_thread,
            args=(args.server_url,),
            daemon=True
        )
        generator_thread.start()
        logger.info("Task generator thread started")

    logger.info(f"Starting in {args.mode} mode")
    logger.info(f"Server URL: {args.server_url}")
    logger.info(f"Worker ID: {worker_id}")

    # Start task manager in main thread
    logger.info("Starting task manager...")
    task_manager = TaskManager(
        server_url=args.server_url,
        worker_id=worker_id,
        poll_interval=args.poll_interval
    )
    task_manager.start()


if __name__ == '__main__':
    main()