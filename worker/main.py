import datetime
import time
import s3fs
import argparse
import threading
import requests

from himawari_processor import available_composites
from task import TaskClient, TaskProcessor
from sync import HimawariDataSync
from utils import logger, _available_latest_time, generate_worker_id
from config import server_url


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

def run_task_generator(server_url, shutdown_event=None):
    """
    Task generator thread that monitors data availability and creates tasks
    
    Args:
        server_url: Server endpoint URL
        shutdown_event: threading.Event to control shutdown (new Event created if None)
    """
    logger.info("Starting Himawari task generator thread...")

    current_target_time = None

    while not shutdown_event.is_set():
        try:
            # Get the latest available time
            latest_time = _available_latest_time()

            # If we don't have a current target time, set it to the latest time
            if current_target_time is None:
                current_target_time = latest_time

            # If the current target time is still in the future compared to latest available, wait
            if current_target_time > latest_time:
                shutdown_event.wait(60)
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

            shutdown_event.wait(60)

        except KeyboardInterrupt:
            logger.info(f"Task generator received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in task generator: {e}")
            shutdown_event.wait(60)

def run_himawari_sync(shutdown_event=None):
    """
    Synchronizes Himawari-9 data from NOAA S3 to local MinIO
    
    Args:
        shutdown_event: threading.Event to control shutdown (new Event created if None)
    """
    if shutdown_event is None:
        shutdown_event = threading.Event()
    
    logger.info("Starting Himawari-9 data synchronization")
    
    # Initialize sync client
    sync_client = HimawariDataSync()
    
    # Start with available latest time
    current_target_time = _available_latest_time()
    logger.info(f"Starting sync from time: {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")

    while not shutdown_event.is_set():
        try:
            # Try to sync current target time
            if sync_client.sync(current_target_time):
                # Successfully synced 160 files, move to next 10-minute interval
                current_target_time = current_target_time + datetime.timedelta(minutes=10)
                logger.info(f"Moving to next time: {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")
            else:
                # Wait with shutdown awareness
                shutdown_event.wait(60)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in sync loop: {e}")
            shutdown_event.wait(60)
    
    logger.info("Himawari sync stopped")

def run_task_manager(server_url, worker_id=None, poll_interval=10, shutdown_event=None):
    """
    Run the task manager with shutdown event control
    
    Args:
        server_url: Server endpoint URL
        worker_id: Optional worker identifier
        poll_interval: Time between task polls in seconds
        shutdown_event: Event to signal shutdown (new Event created if None)
    """
    # Initialize components
    task_client = TaskClient(server_url, worker_id)
    task_processor = TaskProcessor(task_client)
    
    logger.info("Starting task manager (Worker ID: %s)", task_client.worker_id)
    logger.info("Server URL: %s", task_client.server_url)
    logger.info("Poll interval: %s seconds", poll_interval)

    if shutdown_event is None:
        shutdown_event = threading.Event()

    while not shutdown_event.is_set():
        try:
            # Get next task
            task_data = task_client.get_next_task()

            if task_data:
                # Process the task
                task_processor.process_task(task_data)
            else:
                # No tasks available, wait with shutdown awareness
                logger.debug("No tasks available, waiting %s seconds...", poll_interval)
                shutdown_event.wait(poll_interval)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("Task processing error: %s", e, exc_info=True)
            shutdown_event.wait(poll_interval) # Shorter wait on errors


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Himawari satellite data processing')
    parser.add_argument('--task', action='store_true',
                        help='Enable task generator that monitors data availability and creates tasks')
    parser.add_argument('--sync', action='store_true',
                        help='Enable Himawari data synchronization from NOAA S3')
    parser.add_argument('--worker', action='store_true',
                        help='Enable composite worker that processes tasks from the queue')
    parser.add_argument('--worker-id', help='Worker ID (auto-generated if not provided)')

    args = parser.parse_args()

    # Generate worker ID if not provided
    worker_id = args.worker_id or generate_worker_id()
    logger.info(f"Worker ID: {worker_id}")

    # Start background services
    threads = []
    shared_event = threading.Event()
    # Automatic worker activation if no other mode specified
    should_run_worker = args.worker or (not args.task and not args.sync)

    if args.task:
        t = threading.Thread(target=run_task_generator, args=(server_url,), kwargs={'shutdown_event': shared_event})
        threads.append(t)

    if args.sync:
        t = threading.Thread(target=run_himawari_sync, kwargs={'shutdown_event': shared_event})
        threads.append(t)

    if should_run_worker:
        t = threading.Thread(target=run_task_manager, args=(server_url, worker_id,), kwargs={'shutdown_event': shared_event})
        threads.append(t)

    for t in threads:
        t.start()

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        shared_event.set()
        for t in threads:
            t.join(timeout=3)


if __name__ == '__main__':
    main()