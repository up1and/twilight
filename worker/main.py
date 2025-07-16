import time
import datetime
import argparse
import threading
import requests

import s3fs

from himawari_processor import available_composites
from task import TaskClient, TaskProcessor
from sync import SyncClient, SyncProcessor
from utils import logger, _available_latest_time, generate_worker_id
from client import check_local_files
from config import server_url


def check_files(target_time):
    """Check files are available for the given time"""
    try:
        fs = s3fs.S3FileSystem(anon=True)
        s3_path = 'noaa-himawari9/AHI-L1b-FLDK/{}'.format(target_time.strftime('%Y/%m/%d/%H%M'))
        files = fs.ls(s3_path)
        return files

    except Exception as e:
        logger.error(f"Error checking files for time {target_time.strftime('%Y-%m-%d %H:%M')} UTC: {e}")
        return []
    
def get_source_priorty(timestamp):
    from config import data_source
    if data_source == 'auto':
        # Check if it's old data (>1 month), if so, allow remote processing
        one_month_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
        if timestamp > one_month_ago:
            data_source = 'local'
        else:
            data_source = 'remote'

    return data_source

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

            # If the current target time is too far behind, manually move to next interval
            if latest_time - current_target_time > datetime.timedelta(minutes=20):
                current_target_time = current_target_time + datetime.timedelta(minutes=10)

            # If the current target time is still in the future compared to latest available, wait
            if current_target_time > latest_time:
                shutdown_event.wait(60)
                continue

            # Check if files are available
            files = check_files(current_target_time)
            if len(files) >= 160:
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
    sync_client = SyncClient(server_url)
    sync_processor = SyncProcessor(sync_client)
    
    # Start with available latest time
    current_target_time = _available_latest_time()
    target_start_time = datetime.datetime.now(datetime.timezone.utc)
    timeout_minutes = 10  # 10 minutes per target_time
    logger.info(f"Starting sync from time: {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")
    
    # Create pending sync record for initial target time
    sync_client.create_sync(current_target_time)

    def move_to_next(target_time):
        # Move to next 10-minute interval
        target_time += datetime.timedelta(minutes=10)
        # Reset timer for new target_time
        start_time = datetime.datetime.now(datetime.timezone.utc)
        # Create pending sync record for new target time
        sync_client.create_sync(target_time)
        return target_time, start_time

    while not shutdown_event.is_set():
        try:
            # Try to sync current target time
            sync_status = sync_processor.sync(current_target_time)
            if sync_status == 'done':
                # Successfully synced files, move to next 10-minute interval
                current_target_time, target_start_time = move_to_next(current_target_time)
                logger.info(f"Sync completed, moving to next time: {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")
            else:
                # Check if we've spent too much time on this target_time
                current_time = datetime.datetime.now(datetime.timezone.utc)
                elapsed_time = current_time - target_start_time
                if elapsed_time > datetime.timedelta(minutes=timeout_minutes):
                    logger.warning(f"Target time {current_target_time.strftime('%Y-%m-%d %H:%M')} exceeded {timeout_minutes}-minute limit, moving to next")
                    sync_client.update_sync(current_target_time, status='pending')
                    current_target_time, target_start_time = move_to_next(current_target_time)
                else:
                    # Still within time limit, wait and retry
                    logger.info(f"Status: {sync_status}, waiting before retry")
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
            # Peek at next task
            task_data = task_client.peek_next_task()

            if task_data:
                task_id = task_data['task_id']
                timestamp = task_data['timestamp']
                source = get_source_priorty(timestamp)
                
                # Check if we can process this task
                if source == 'remote' or (source == 'local' and check_local_files(timestamp)):
                    # Claim the task before processing
                    claimed_task = task_client.claim_task(task_id)
                    if claimed_task:
                        # Successfully claimed, now process it
                        task_processor.process_task(claimed_task, source)
                    else:
                        # Task was claimed by another worker or no longer available
                        logger.debug("Task %s was claimed by another worker, trying next task...", task_id)
                        continue
                else:
                    logger.debug("Task skipped, %s files not exist, waiting %s seconds...", source, poll_interval)
                    shutdown_event.wait(poll_interval)
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