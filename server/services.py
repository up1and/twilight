"""
Service classes for business logic
"""
import json
import datetime

from models import TaskModel, SyncModel


class TaskManager:
    def __init__(self, redis_client, expire_days=7):
        self.redis = redis_client
        # Redis keys
        self.tasks_key = "tasks"  # Hash: task_id -> task_json
        self.queue_key = "task_queue"  # Sorted Set: task_id with priority+timestamp score
        self.expire_time = expire_days * 86400 if expire_days > 0 else None

        # Redis lock for distributed locking
        self.lock = self.redis.lock("task_lock", timeout=10, blocking_timeout=10)

        # Priority weights for scoring (lower score = higher priority)
        self.priority_weights = {"high": 0, "normal": 1000000, "low": 2000000}

    def _calculate_score(self, task):
        """Calculate score for sorted set (lower score = higher priority)"""
        priority_weight = self.priority_weights.get(task.priority, 1000000)
        # Use timestamp as seconds since epoch for fine-grained ordering
        timestamp_score = int(task.timestamp.timestamp())
        return priority_weight + timestamp_score

    def create_task(self, composite, timestamp, priority="normal"):
        """Create a new task with deduplication and optional priority promotion"""
        with self.lock:
            # Create a temporary task for comparison
            temp_task = TaskModel(composite, timestamp, priority)

            # Check for existing task using __eq__ method
            existing_tasks = self._get_all_tasks()
            for existing_task in existing_tasks:
                if (existing_task == temp_task and
                    existing_task.status in ["pending", "running"]):
                    # Task already exists, return existing task
                    return existing_task

            # Create new task if no duplicate found
            task = temp_task

            # Store task in Redis
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())

            # Add to sorted set with calculated score
            score = self._calculate_score(task)
            self.redis.zadd(self.queue_key, {task.task_id: score})

            if self.expire_time:
                self.redis.expire(self.tasks_key, self.expire_time)
            return task

    def _get_all_tasks(self):
        """Get all tasks from Redis"""
        task_data = self.redis.hgetall(self.tasks_key)
        tasks = []
        for task_json in task_data.values():
            tasks.append(TaskModel.from_json(task_json))
        return tasks

    def promote_tasks(self, timestamp):
        """Promote pending normal priority tasks with matching timestamp to high priority"""
        with self.lock:
            # Get all task IDs from the queue (only pending tasks are in queue)
            task_ids = self.redis.zrange(self.queue_key, 0, -1)

            # Process tasks that need promotion
            promoted_tasks = []
            for task_id in task_ids:
                task_json = self.redis.hget(self.tasks_key, task_id)
                if task_json:
                    task = TaskModel.from_json(task_json)
                    # Check if task timestamp matches and priority is not already high
                    if (task.priority == "normal" and task.timestamp == timestamp):
                        task.priority = "high"
                        promoted_tasks.append(task)

            # Update promoted tasks
            for task in promoted_tasks:
                # Update task data
                self.redis.hset(self.tasks_key, task.task_id, task.to_json())
                # Update score in sorted set
                new_score = self._calculate_score(task)
                self.redis.zadd(self.queue_key, {task.task_id: new_score})

    def get_task(self, task_id):
        """Get task by ID"""
        task_json = self.redis.hget(self.tasks_key, task_id)
        if task_json:
            return TaskModel.from_json(task_json)
        return None

    def peek_next_task(self, priorities=None, composites=None):
        """Peek at the next pending task without removing it from queue

        Args:
            priorities: Priority filter - list of priorities, empty list means all
            composites: Composite filter - list of composite names, empty list means all

        Returns:
            TaskModel or None: Next matching task or None if no tasks match
        """
        with self.lock:
            # Get all task IDs from queue (ordered by priority)
            task_ids = self.redis.zrange(self.queue_key, 0, -1)
            if not task_ids:
                return None

            for task_id in task_ids:
                task_json = self.redis.hget(self.tasks_key, task_id)
                if not task_json:
                    # Task was deleted, remove from queue
                    self.redis.zrem(self.queue_key, task_id)
                    continue

                task = TaskModel.from_json(task_json)

                # Filter by priority
                if not self._matches(task.priority, priorities):
                    continue

                # Filter by composite
                if not self._matches(task.composite, composites):
                    continue

                # Found a matching task
                return task

            # No matching tasks found
            return None

    def _matches(self, value, filters):
        """Check if value matches any of the filters"""
        return not filters or value in filters

    def claim_task(self, task_id, worker_id):
        """Claim a specific task and mark it as processing"""
        with self.lock:
            # Check if task still exists in queue
            if not self.redis.zscore(self.queue_key, task_id):
                return None

            # Get task data
            task_json = self.redis.hget(self.tasks_key, task_id)
            if not task_json:
                # Task was deleted, remove from queue
                self.redis.zrem(self.queue_key, task_id)
                return None

            task = TaskModel.from_json(task_json)
            task.status = "running"
            task.started = datetime.datetime.now(datetime.timezone.utc)
            task.worker_id = worker_id

            # Remove from queue and update task status
            self.redis.zrem(self.queue_key, task_id)
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())

            return task

    def update_task_status(self, task_id, status, message=None):
        """Update task status"""
        with self.lock:
            task_json = self.redis.hget(self.tasks_key, task_id)
            if not task_json:
                return False

            task = TaskModel.from_json(task_json)
            task.status = status
            if message:
                task.message = message
            if status in ["completed", "failed"]:
                task.ended = datetime.datetime.now(datetime.timezone.utc)

            # Update task in Redis
            self.redis.hset(self.tasks_key, task.task_id, task.to_json())
            if self.expire_time:
                self.redis.expire(self.tasks_key, self.expire_time)
            return True

    def get_tasks(self, status=None, composite=None, priority=None, limit=20, offset=0):
        """Get tasks with optional filtering"""
        all_tasks = self._get_all_tasks()
        filtered_tasks = []

        for task in all_tasks:
            if status and task.status != status:
                continue
            if composite and task.composite != composite:
                continue
            if priority and task.priority != priority:
                continue
            filtered_tasks.append(task)

        # Sort by created desc
        filtered_tasks.sort(key=lambda t: t.created, reverse=True)

        return filtered_tasks[offset:offset+limit], len(filtered_tasks)
    
    def save_profile(self, task_id, tasks, resources):
        """Save profiler data for a task"""
        profile_key = f"profiles:{task_id}"
        if tasks:
            self.redis.set(f"{profile_key}:tasks", json.dumps(tasks))
        if resources:
            self.redis.set(f"{profile_key}:resources", json.dumps(resources))
        
        if self.expire_time:
            self.redis.expire(f"{profile_key}:tasks", self.expire_time)
            self.redis.expire(f"{profile_key}:resources", self.expire_time)

    def get_profile(self, task_id):
        """Get profiler data for a task"""
        profile_key = f"profiles:{task_id}"
        tasks_data = self.redis.get(f"{profile_key}:tasks")
        resources_data = self.redis.get(f"{profile_key}:resources")
        if not tasks_data and not resources_data:
            return None
        return {"tasks": json.loads(tasks_data), "resources": json.loads(resources_data)}

class SyncManager:
    def __init__(self, redis_client, task_manager=None, expire_days=30):
        self.redis = redis_client
        self.task_manager = task_manager
        # Redis keys
        self.syncs_key = "syncs"  # Hash: timestamp_key -> sync_json
        self.timestamps_key = "syncs_timestamps"  # Sorted Set: timestamp_key with unix timestamp score
        self.expire_time = expire_days * 86400 if expire_days > 0 else None

        # Redis lock for distributed locking
        self.lock = self.redis.lock("syncs_lock", timeout=10, blocking_timeout=10)

    def _get_timestamp_key(self, source, timestamp):
        """Get timestamp key for Redis storage"""
        return f"{source}:{timestamp.strftime('%Y%m%d_%H%M')}"

    def create_sync(self, source, timestamp):
        """Create a pending sync record for a timestamp"""
        timestamp_key = self._get_timestamp_key(source, timestamp)
        with self.lock:
            # Check if already exists
            if self.redis.hexists(self.syncs_key, timestamp_key):
                return

            # Create new sync
            sync = SyncModel(source, timestamp)

            # Store sync in Redis hash
            self.redis.hset(self.syncs_key, timestamp_key, sync.to_json())
            
            # Add to sorted set with unix timestamp as score
            score = int(timestamp.timestamp())
            self.redis.zadd(self.timestamps_key, {timestamp_key: score})

            # Set expiration
            if self.expire_time:
                self.redis.expire(self.syncs_key, self.expire_time)
                self.redis.expire(self.timestamps_key, self.expire_time)
    def update_progress(self, source, timestamp, status=None, files=None, size=None):
        """Update sync progress for a timestamp with partial updates
        
        Args:
            source: Data source (required)
            timestamp: Target datetime (required)
            status: Status to update (optional)
            files: Number of files to update (optional)
            size: Total size to update (optional)
        """
        timestamp_key = self._get_timestamp_key(source, timestamp)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        with self.lock:
            # Get existing sync
            sync_json = self.redis.hget(self.syncs_key, timestamp_key)
            if sync_json:
                sync = SyncModel.from_json(sync_json)
            else:
                # Create new sync if doesn't exist
                sync = SyncModel(source, timestamp)
            
            # Update only provided fields
            if status is not None:
                # If status changed to "completed", promote related tasks to high priority
                if self.task_manager and status == "completed" and sync.status != "completed":
                    self.task_manager.promote_tasks(timestamp)

                sync.status = status
                # Set started time when status becomes running
                if status == "running" and sync.started is None:
                    sync.started = now
            
            if files is not None:
                sync.files = files
                
            if size is not None:
                sync.size = size
                
            # Always update ended time when any field is updated
            sync.ended = now
                
            # Store updated
            self.redis.hset(self.syncs_key, timestamp_key, sync.to_json())
            
            # Ensure it's in sorted set
            score = int(timestamp.timestamp())
            self.redis.zadd(self.timestamps_key, {timestamp_key: score})
            
            # Set expiration
            if self.expire_time:
                self.redis.expire(self.syncs_key, self.expire_time)
                self.redis.expire(self.timestamps_key, self.expire_time)
        
    def get_sync(self, source, timestamp):
        """Get sync status for a timestamp"""
        timestamp_key = self._get_timestamp_key(source, timestamp)
        sync_json = self.redis.hget(self.syncs_key, timestamp_key)
        if not sync_json:
            return None
        return SyncModel.from_json(sync_json).to_dict()
        
    def get_syncs(self, source=None, limit=20, offset=0):
        """Get sync records with pagination and optional source filtering"""
        timestamp_keys = self.redis.zrevrange(self.timestamps_key, 0, -1)
        results = []
        
        for timestamp_key in timestamp_keys:
            sync_json = self.redis.hget(self.syncs_key, timestamp_key)
            if sync_json:
                sync = SyncModel.from_json(sync_json)
                if source is None or sync.source == source:
                    results.append(sync.to_dict())
        
        total = len(results)
        # Apply pagination on filtered results
        paginated_results = results[offset : offset + limit]
                
        return paginated_results, total


class CompositeStateManager:
    """
    Manages composite state in Redis for multi-worker consistency
    """
    
    def __init__(self, redis_client, composite_states):
        self.key = "composite_state"
        self.redis_client = redis_client
        
        # Redis lock for distributed locking
        self.lock = self.redis_client.lock("composite_state_lock", timeout=10, blocking_timeout=10)

        for composite, timestamp in composite_states.items():
            # During initialization, always update to ensure all states are properly set in Redis
            # This ensures consistency even when both current and new values are None
            self.update(composite, timestamp)
    
    def get(self, composite=None):
        """
        Get composite state(s). If composite is None, return all states.
        """
        # All composite states
        result = {}
        composite_states = self.redis_client.hgetall(self.key)
        for composite_name, timestamp_str in composite_states.items():
            if timestamp_str:  # Empty string is falsy
                try:
                    result[composite_name] = datetime.datetime.fromisoformat(timestamp_str)
                except ValueError:
                    result[composite_name] = None
            else:
                result[composite_name] = None

        if composite:
            return result.get(composite)
        
        return result
    
    def update(self, composite, timestamp):
        """
        Update composite state with distributed locking.
        Returns True if updated, False if not.
        """
        with self.lock:
            if timestamp is None:
                timestamp_str = ""  # Store empty string
            else:
                timestamp_str = timestamp.isoformat()
            self.redis_client.hset(self.key, composite, timestamp_str)
