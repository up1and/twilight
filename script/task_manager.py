import datetime
import time
import requests
import socket
import os

from utils import logger


class TaskClient:
    """Client for communicating with the task server"""

    def __init__(self, server_url, worker_id=None):
        self.server_url = server_url.rstrip('/')
        self.worker_id = worker_id or f"worker_{socket.gethostname()}_{os.getpid()}"
        self.session = requests.Session()

    def get_next_task(self):
        """Get next pending task from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/tasks/next",
                params={'worker_id': self.worker_id},
                timeout=10
            )

            if response.status_code == 204:  # No Content
                return None
            elif response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get next task: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting next task: {e}")
            return None

    def update_task_status(self, task_id, status, error_message=None):
        """Update task status on server"""
        try:
            data = {
                'status': status,
                'worker_id': self.worker_id
            }
            if error_message:
                data['error_message'] = error_message

            response = self.session.put(
                f"{self.server_url}/api/tasks/{task_id}/status",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Failed to update task status: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            return False


class TaskProcessor:
    """Processes individual tasks"""

    def __init__(self, task_client: TaskClient):
        self.task_client = task_client

    def process_task(self, task_data):
        """Process a single task"""
        task_id = task_data['task_id']
        composite = task_data['composite']
        timestamp_str = task_data['timestamp']

        try:
            # Parse timestamp
            timestamp = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)

            logger.info(f"Starting task {task_id}: {composite} at {timestamp.strftime('%Y-%m-%d %H:%M')} UTC")

            # Import here to avoid circular imports
            from himawari_processor import process_composite

            # Process the composite
            success = process_composite(composite, timestamp, task_id)

            if success:
                # Report completion
                self.task_client.update_task_status(task_id, 'completed')
                logger.info(f"Task {task_id} completed successfully")
                return True
            else:
                # Report failure
                self.task_client.update_task_status(task_id, 'failed',
                    error_message=f'Processing failed for {composite}')
                logger.error(f"Task {task_id} failed")
                return False

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            self.task_client.update_task_status(task_id, 'failed',
                error_message=str(e))
            return False


class TaskManager:
    """Main task manager that coordinates task processing"""

    def __init__(self, server_url, worker_id=None, poll_interval=30):
        self.task_client = TaskClient(server_url, worker_id)
        self.task_processor = TaskProcessor(self.task_client)
        self.poll_interval = poll_interval
        self.running = False

    def start(self):
        """Start the task manager"""
        logger.info(f"Starting task manager with worker ID: {self.task_client.worker_id}")
        logger.info(f"Server URL: {self.task_client.server_url}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")

        self.running = True

        while self.running:
            try:
                # Get next task
                task_data = self.task_client.get_next_task()

                if task_data:
                    # Process the task
                    self.task_processor.process_task(task_data)
                else:
                    # No tasks available, wait before polling again
                    logger.debug(f"No tasks available, waiting {self.poll_interval} seconds...")
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Unexpected error in task manager: {e}", exc_info=True)
                logger.info(f"Waiting {self.poll_interval} seconds before retrying...")
                time.sleep(self.poll_interval)

    def stop(self):
        """Stop the task manager"""
        self.running = False
