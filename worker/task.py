import os
import socket
import datetime

import requests

from utils import logger


class TaskClient:
    """Client for communicating with the task server"""

    def __init__(self, server_url, worker_id=None):
        self.server_url = server_url.rstrip('/')
        self.worker_id = worker_id or f"worker_{socket.gethostname()}_{os.getpid()}"
        self.session = requests.Session()

    def peek_next_task(self, priorities=None, composites=None):
        """Peek next pending task from server with optional filtering
        
        Args:
            priority: Priority filter - list of priorities, empty list means all
            composite: Composite filter - list of composite names, empty list means all
        """
        try:
            # Build query parameters
            params = {}
            if priorities and len(priorities) > 0:
                params['priority'] = ','.join(priorities)
            
            if composites and len(composites) > 0:
                params['composite'] = ','.join(composites)
            
            response = self.session.get(
                f"{self.server_url}/api/tasks/next",
                params=params,
                timeout=10
            )

            if response.status_code == 204:  # No Content
                return None
            elif response.status_code == 200:
                data = response.json()
                # Parse timestamp
                timestamp = datetime.datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)

                data['timestamp'] = timestamp
                return data
            else:
                logger.error(f"Failed to peek next task: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error peeking next task: {e}")
            return None

    def claim_task(self, task_id):
        """Claim a specific task for processing"""
        try:
            data = {
                'worker_id': self.worker_id
            }

            response = self.session.put(
                f"{self.server_url}/api/tasks/{task_id}/claim",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                # Parse timestamp
                timestamp = datetime.datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)

                data['timestamp'] = timestamp
                return data
            else:
                logger.error(f"Failed to claim task: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error claiming task: {e}")
            return None

    def update_task_status(self, task_id, status, message=None):
        """Update task status on server"""
        try:
            data = {
                'status': status,
                'worker_id': self.worker_id
            }
            if message:
                data['message'] = message

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

    def __init__(self, task_client: TaskClient, cache_manager):
        self.task_client = task_client
        self.cache_manager = cache_manager

    def process_task(self, task_data, data_source='remote'):
        """Process a single task"""
        task_id = task_data['task_id']
        composite = task_data['composite']
        timestamp = task_data['timestamp']

        try:
            logger.info(f"Starting task {task_id}: {composite} at {timestamp.strftime('%Y-%m-%d %H:%M')} UTC")

            # Import here to avoid circular imports
            from himawari_processor import process_composite
            # Clean up cache before processing
            self.cache_manager.cleanup_cache()

            # Process the composite
            process_composite(composite, timestamp, data_source)
            # Report completion
            self.task_client.update_task_status(task_id, 'completed')
            logger.info(f"Task {task_id} completed successfully")
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            self.task_client.update_task_status(task_id, 'failed', message=str(e))
