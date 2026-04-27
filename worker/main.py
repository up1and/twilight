import time
import datetime
import argparse
import threading
import requests

from himawari_processor import cache_dir
from task import TaskClient, TaskProcessor
from sync import SyncClient, SyncProcessor
from utils import logger, _available_latest_time, generate_worker_id, CacheManager
from config import server_url, auth_key, cache_size_limit, priorities, composites, \
    max_resolution, bbox, resampler, mem_per_worker, system_margin


def resolve_data_source(server_url, timestamp, auth_key=None):
    """
    Check sync status to determine data source and processing decision
    
    Args:
        server_url: Server endpoint URL
        auth_key: Authentication key
        timestamp: Target datetime
        
    Returns:
        string: data_source ("local", "remote" or "pending")
    """
    headers = {"Authorization": f"Bearer {auth_key}"} if auth_key else {}
    try:
        response = requests.get(
            f"{server_url}/api/syncs/{timestamp.isoformat()}",
            params={"source": "himawari"},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "pending")
            
            if status == "completed":
                # Sync data is complete, use local MinIO
                return "local"
            elif status == "running":
                # Sync data is still running, wait
                return "pending"
            else:  # status == "pending" or other
                # Sync data not available, use NOAA remote
                return "remote"
        else:
            logger.warning(f"Failed to check sync data status: {response.status_code} {response.text}")
            # Default to remote on error
            return "remote"
            
    except Exception as e:
        logger.error(f"Error checking sync data status: {e}")
        # Default to remote on error
        return "remote"

def run_himawari_sync(auth_key=None, shutdown_event=None):
    """
    Synchronizes Himawari-9 data from NOAA S3 to local MinIO
    
    Args:
        shutdown_event: threading.Event to control shutdown (new Event created if None)
    """
    if shutdown_event is None:
        shutdown_event = threading.Event()
    
    logger.info("Starting Himawari-9 data synchronization")
    
    # Initialize sync client
    sync_client = SyncClient(server_url, auth_key)
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
            if sync_status == "completed":
                # Successfully synced files, move to next 10-minute interval
                current_target_time, target_start_time = move_to_next(current_target_time)
                logger.info(f"Sync completed, moving to next time: {current_target_time.strftime('%Y-%m-%d %H:%M')} UTC")
            else:
                # Check if we've spent too much time on this target_time
                current_time = datetime.datetime.now(datetime.timezone.utc)
                elapsed_time = current_time - target_start_time
                if elapsed_time > datetime.timedelta(minutes=timeout_minutes):
                    logger.warning(f"Target time {current_target_time.strftime('%Y-%m-%d %H:%M')} exceeded {timeout_minutes}-minute limit, moving to next")
                    sync_client.update_sync(current_target_time, status="failed")
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

def run_task_manager(server_url, auth_key=None, worker_id=None, poll_interval=10, shutdown_event=None):
    """
    Run the task manager with shutdown event control
    
    Args:
        server_url: Server endpoint URL
        auth_key: Authentication key
        worker_id: Optional worker identifier
        poll_interval: Time between task polls in seconds
        shutdown_event: Event to signal shutdown (new Event created if None)
    """
    # Initialize components
    task_client = TaskClient(server_url, auth_key, worker_id)
    cache_manager = CacheManager(cache_dir, cache_size_limit)
    task_processor = TaskProcessor(
        task_client, 
        cache_manager, 
        max_resolution=max_resolution, 
        bbox=bbox,
        resampler=resampler,
        mem_per_worker=mem_per_worker,
        system_margin=system_margin
    )
    
    logger.info("Starting task manager (Worker ID: %s)", task_client.worker_id)
    logger.info("Server URL: %s", task_client.server_url)
    logger.info("Poll interval: %s seconds", poll_interval)

    if shutdown_event is None:
        shutdown_event = threading.Event()

    while not shutdown_event.is_set():
        try:
            # Peek at next task with filtering
            task_data = task_client.peek_next_task(
                priorities=priorities,
                composites=composites
            )

            if task_data:
                task_id = task_data["task_id"]
                timestamp = task_data["timestamp"]
                
                # Check raw data status to determine data source
                source = resolve_data_source(server_url, timestamp, auth_key)
                
                if source != "pending":
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
                    # Sync raw data is still running, wait before checking again
                    logger.debug("Sync raw data for %s is still running, waiting %s seconds...", 
                               timestamp.strftime('%Y-%m-%d %H:%M'), poll_interval)
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
    parser = argparse.ArgumentParser(description="Himawari satellite data processing")
    parser.add_argument("--sync", action="store_true",
                        help="Enable Himawari data synchronization from NOAA S3")
    parser.add_argument("--worker", action="store_true",
                        help="Enable composite worker that processes tasks from the queue")
    parser.add_argument("--worker-id", help="Worker ID (auto-generated if not provided)")

    args = parser.parse_args()

    # Generate worker ID if not provided
    worker_id = args.worker_id or generate_worker_id()
    logger.info(f"Worker ID: {worker_id}")

    # Start background services
    threads = []
    shared_event = threading.Event()
    # Automatic worker activation if no other mode specified
    should_run_worker = args.worker or not args.sync

    if args.sync:
        t = threading.Thread(target=run_himawari_sync, args=(auth_key,), kwargs={"shutdown_event": shared_event})
        threads.append(t)

    if should_run_worker:
        t = threading.Thread(target=run_task_manager, args=(server_url, auth_key, worker_id,), kwargs={"shutdown_event": shared_event}, daemon=True)
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


if __name__ == "__main__":
    main()