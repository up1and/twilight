"""
Data models for the application
"""
import json
import uuid
import datetime


class TaskModel:
    def __init__(self, composite, timestamp, priority="normal"):
        self.task_id = f"{composite}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.composite = composite
        self.timestamp = timestamp
        self.priority = priority
        self.status = "pending"  # pending, running, completed, failed
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.started = None
        self.ended = None
        self.worker_id = None
        self.message = None

    def __eq__(self, other):
        """Compare tasks based on composite and timestamp"""
        if not isinstance(other, TaskModel):
            return False
        return (self.composite == other.composite and
                self.timestamp == other.timestamp)

    def __hash__(self):
        """Make Task hashable for use in sets and as dict keys"""
        return hash((self.composite, self.timestamp))

    @property
    def duration(self):
        """Calculate task duration in seconds"""
        if self.started and self.ended:
            return (self.ended - self.started).total_seconds()
        return None

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "composite": self.composite,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "status": self.status,
            "created": self.created,
            "started": self.started if self.started else None,
            "ended": self.ended if self.ended else None,
            "duration": self.duration,
            "worker_id": self.worker_id,
            "message": self.message
        }

    def to_json(self):
        """Serialize task to JSON string for Redis storage"""
        data = self.to_dict()
        # Convert datetime objects to ISO format strings
        for key in ["timestamp", "created", "started", "ended"]:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str):
        """Deserialize task from JSON string"""
        data = json.loads(json_str)

        # Create task instance
        task = cls.__new__(cls)
        task.task_id = data["task_id"]
        task.composite = data["composite"]
        task.priority = data["priority"]
        task.status = data["status"]
        task.worker_id = data["worker_id"]
        task.message = data["message"]

        # Convert ISO format strings back to datetime objects
        task.timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        task.created = datetime.datetime.fromisoformat(data["created"])
        task.started = datetime.datetime.fromisoformat(data["started"]) if data["started"] else None
        task.ended = datetime.datetime.fromisoformat(data["ended"]) if data["ended"] else None

        return task


class SyncModel:
    def __init__(self, source, timestamp):
        self.source = source
        self.timestamp = timestamp
        self.status = "pending"  # pending, running, completed, failed
        self.files = 0
        self.size = 0
        self.started = None
        self.ended = None
        self.created = datetime.datetime.now(datetime.timezone.utc)

    @property
    def duration(self):
        """Calculate sync duration in seconds"""
        if self.started and self.ended:
            return int((self.ended - self.started).total_seconds())
        return None
        
    @property
    def speed(self):
        """Calculate download speed in KB/s"""
        if self.duration and self.duration > 0 and self.size > 0:
            # Convert bytes to kilobytes and divide by duration
            return int(self.size / 1024 / self.duration)
        return None

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "status": self.status,
            "files": self.files,
            "size": self.size,
            "started": self.started if self.started else None,
            "ended": self.ended if self.ended else None,
            "duration": self.duration,
            "speed": self.speed,
            "created": self.created
        }

    def to_json(self):
        """Serialize raw to JSON string for Redis storage"""
        data = {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source,
            "status": self.status,
            "files": self.files,
            "size": self.size,
            "started": self.started.isoformat() if self.started else None,
            "ended": self.ended.isoformat() if self.ended else None,
            "created": self.created.isoformat() if self.created else None
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str):
        """Deserialize raw from JSON string"""
        data = json.loads(json_str)

        # Create raw instance
        sync = cls.__new__(cls)
        sync.source = data["source"]
        sync.status = data["status"]
        sync.files = data["files"]
        sync.size = data["size"]

        # Convert ISO format strings back to datetime objects
        sync.timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        sync.created = datetime.datetime.fromisoformat(data["created"])
        sync.started = datetime.datetime.fromisoformat(data["started"]) if data["started"] else None
        sync.ended = datetime.datetime.fromisoformat(data["ended"]) if data["ended"] else None

        return sync
