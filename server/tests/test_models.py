"""
Tests for data models
"""
import datetime
from server.models import TaskModel, SyncModel


class TestTaskModel:
    """Test TaskModel class"""
    
    def test_task_creation(self, sample_timestamp):
        task = TaskModel("ir_clouds", sample_timestamp, "high")
        
        assert task.composite == "ir_clouds"
        assert task.timestamp == sample_timestamp
        assert task.priority == "high"
        assert task.status == "pending"
        assert task.worker_id is None
        assert task.message is None
        assert task.started is None
        assert task.ended is None
        assert isinstance(task.created, datetime.datetime)
        assert task.task_id.startswith("ir_clouds_20250115_120000_")
    
    def test_task_equality(self, sample_timestamp):
        task1 = TaskModel("ir_clouds", sample_timestamp, "normal")
        task2 = TaskModel("ir_clouds", sample_timestamp, "high")  # Different priority
        task3 = TaskModel("true_color", sample_timestamp, "normal")  # Different composite
        
        # Same composite and timestamp should be equal regardless of priority
        assert task1 == task2
        assert task1 != task3
        
        # Test equality with non-TaskModel object
        assert task1 != "not a task"
        assert task1 != None
        assert task1 != 123
    
    def test_task_hash(self, sample_timestamp):
        task1 = TaskModel("ir_clouds", sample_timestamp, "normal")
        task2 = TaskModel("ir_clouds", sample_timestamp, "high")
        
        # Should have same hash for same composite and timestamp
        assert hash(task1) == hash(task2)
    
    def test_duration_calculation(self, sample_timestamp):
        task = TaskModel("ir_clouds", sample_timestamp)
        
        # No duration when not started/ended
        assert task.duration is None
        
        # Set started and ended times
        task.started = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        task.ended = datetime.datetime(2025, 1, 15, 12, 5, 30, tzinfo=datetime.timezone.utc)
        
        assert task.duration == 330.0  # 5 minutes 30 seconds
    
    def test_to_dict(self, sample_timestamp):
        task = TaskModel("ir_clouds", sample_timestamp, "high")
        task.worker_id = "worker-123"
        task.message = "Processing..."
        
        result = task.to_dict()
        
        assert result["composite"] == "ir_clouds"
        assert result["timestamp"] == sample_timestamp
        assert result["priority"] == "high"
        assert result["status"] == "pending"
        assert result["worker_id"] == "worker-123"
        assert result["message"] == "Processing..."
        assert result["duration"] is None
    
    def test_json_serialization(self, sample_timestamp):
        task = TaskModel("ir_clouds", sample_timestamp, "normal")
        
        # Serialize to JSON
        json_str = task.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize from JSON
        restored_task = TaskModel.from_json(json_str)
        
        assert restored_task.composite == task.composite
        assert restored_task.timestamp == task.timestamp
        assert restored_task.priority == task.priority
        assert restored_task.status == task.status
        assert restored_task.created == task.created


class TestSyncModel:
    """Test SyncModel class"""
    
    def test_sync_creation(self, sample_timestamp):
        sync = SyncModel("himawari", sample_timestamp)
        
        assert sync.source == "himawari"
        assert sync.timestamp == sample_timestamp
        assert sync.status == "pending"
        assert sync.files == 0
        assert sync.size == 0
        assert sync.started is None
        assert sync.ended is None
        assert isinstance(sync.created, datetime.datetime)
    
    def test_duration_calculation(self, sample_timestamp):
        sync = SyncModel("himawari", sample_timestamp)
        
        # No duration when not started/ended
        assert sync.duration is None
        
        # Set started and ended times
        sync.started = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        sync.ended = datetime.datetime(2025, 1, 15, 12, 3, 0, tzinfo=datetime.timezone.utc)
        
        assert sync.duration == 180  # 3 minutes
    
    def test_speed_calculation(self, sample_timestamp):
        sync = SyncModel("himawari", sample_timestamp)
        
        # No speed when no duration or size
        assert sync.speed is None
        
        # Set values for speed calculation
        sync.started = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        sync.ended = datetime.datetime(2025, 1, 15, 12, 1, 0, tzinfo=datetime.timezone.utc)  # 60 seconds
        sync.size = 1024 * 100  # 100 KB
        
        assert sync.speed == int(100 / 60)  # ~1 KB/s
    
    def test_to_dict(self, sample_timestamp):
        sync = SyncModel("himawari", sample_timestamp)
        sync.status = "completed"
        sync.files = 10
        sync.size = 1024000
        
        result = sync.to_dict()
        
        assert result["source"] == "himawari"
        assert result["timestamp"] == sample_timestamp
        assert result["status"] == "completed"
        assert result["files"] == 10
        assert result["size"] == 1024000
        assert result["duration"] is None
        assert result["speed"] is None
    
    def test_json_serialization(self, sample_timestamp):
        sync = SyncModel("himawari", sample_timestamp)
        sync.status = "running"
        sync.files = 5
        sync.size = 512000
        
        # Serialize to JSON
        json_str = sync.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize from JSON
        restored_sync = SyncModel.from_json(json_str)
        
        assert restored_sync.source == sync.source
        assert restored_sync.timestamp == sync.timestamp
        assert restored_sync.status == sync.status
        assert restored_sync.files == sync.files
        assert restored_sync.size == sync.size
        assert restored_sync.created == sync.created
