"""
Tests for data models
"""
import datetime
from server.models import TaskModel, HimawariRawModel


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


class TestHimawariRawModel:
    """Test HimawariRawModel class"""
    
    def test_raw_creation(self, sample_timestamp):
        raw = HimawariRawModel(sample_timestamp)
        
        assert raw.timestamp == sample_timestamp
        assert raw.status == "pending"
        assert raw.files == 0
        assert raw.size == 0
        assert raw.started is None
        assert raw.ended is None
        assert isinstance(raw.created, datetime.datetime)
    
    def test_duration_calculation(self, sample_timestamp):
        raw = HimawariRawModel(sample_timestamp)
        
        # No duration when not started/ended
        assert raw.duration is None
        
        # Set started and ended times
        raw.started = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        raw.ended = datetime.datetime(2025, 1, 15, 12, 3, 0, tzinfo=datetime.timezone.utc)
        
        assert raw.duration == 180  # 3 minutes
    
    def test_speed_calculation(self, sample_timestamp):
        raw = HimawariRawModel(sample_timestamp)
        
        # No speed when no duration or size
        assert raw.speed is None
        
        # Set values for speed calculation
        raw.started = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        raw.ended = datetime.datetime(2025, 1, 15, 12, 1, 0, tzinfo=datetime.timezone.utc)  # 60 seconds
        raw.size = 1024 * 100  # 100 KB
        
        assert raw.speed == int(100 / 60)  # ~1 KB/s
    
    def test_to_dict(self, sample_timestamp):
        raw = HimawariRawModel(sample_timestamp)
        raw.status = "completed"
        raw.files = 10
        raw.size = 1024000
        
        result = raw.to_dict()
        
        assert result["timestamp"] == sample_timestamp
        assert result["status"] == "completed"
        assert result["files"] == 10
        assert result["size"] == 1024000
        assert result["duration"] is None
        assert result["speed"] is None
    
    def test_json_serialization(self, sample_timestamp):
        raw = HimawariRawModel(sample_timestamp)
        raw.status = "running"
        raw.files = 5
        raw.size = 512000
        
        # Serialize to JSON
        json_str = raw.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize from JSON
        restored_raw = HimawariRawModel.from_json(json_str)
        
        assert restored_raw.timestamp == raw.timestamp
        assert restored_raw.status == raw.status
        assert restored_raw.files == raw.files
        assert restored_raw.size == raw.size
        assert restored_raw.created == raw.created
