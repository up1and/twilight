"""
Tests for service classes
"""
from unittest.mock import Mock
from server.services import TaskManager, HimawariRawManager
from server.models import TaskModel, HimawariRawModel


class TestTaskManager:
    """Test TaskManager class"""
    
    def test_init(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        assert manager.redis == mock_redis
        assert manager.tasks_key == 'tasks'
        assert manager.queue_key == 'task_queue'
        assert manager.expire_time == 3600 * 24 * 7
    
    def test_calculate_score(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Test high priority
        task_high = TaskModel('ir_clouds', sample_timestamp, 'high')
        score_high = manager._calculate_score(task_high)
        
        # Test normal priority
        task_normal = TaskModel('ir_clouds', sample_timestamp, 'normal')
        score_normal = manager._calculate_score(task_normal)
        
        # Test low priority
        task_low = TaskModel('ir_clouds', sample_timestamp, 'low')
        score_low = manager._calculate_score(task_low)
        
        # High priority should have lower score (higher priority)
        assert score_high < score_normal < score_low
    
    def test_create_task_new(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Mock no existing tasks
        mock_redis.hgetall.return_value = {}
        
        task = manager.create_task('ir_clouds', sample_timestamp, 'normal')
        
        assert task.composite == 'ir_clouds'
        assert task.timestamp == sample_timestamp
        assert task.priority == 'normal'
        assert task.status == 'pending'
        
        # Verify Redis calls
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()
        mock_redis.expire.assert_called()
    
    def test_create_task_duplicate(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Create existing task
        existing_task = TaskModel('ir_clouds', sample_timestamp, 'normal')
        existing_task.status = 'pending'
        
        # Mock existing task in Redis
        mock_redis.hgetall.return_value = {
            existing_task.task_id: existing_task.to_json()
        }
        
        # Try to create duplicate
        result = manager.create_task('ir_clouds', sample_timestamp, 'high')
        
        # Should return existing task
        assert result.task_id == existing_task.task_id
        assert result.status == 'pending'
    
    def test_get_task_exists(self, mock_redis, sample_task):
        manager = TaskManager(mock_redis)
        
        # Mock task exists in Redis
        mock_redis.hget.return_value = sample_task.to_json()
        
        result = manager.get_task(sample_task.task_id)
        
        assert result.task_id == sample_task.task_id
        assert result.composite == sample_task.composite
        mock_redis.hget.assert_called_with('tasks', sample_task.task_id)
    
    def test_get_task_not_exists(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        # Mock task doesn't exist
        mock_redis.hget.return_value = None
        
        result = manager.get_task('nonexistent-task')
        
        assert result is None
    
    def test_peek_next_task(self, mock_redis, sample_task):
        manager = TaskManager(mock_redis)
        
        # Mock task in queue
        mock_redis.zrange.return_value = [sample_task.task_id]
        mock_redis.hget.return_value = sample_task.to_json()
        
        result = manager.peek_next_task()
        
        assert result.task_id == sample_task.task_id
        mock_redis.zrange.assert_called_with('task_queue', 0, -1)
    
    def test_peek_next_task_empty_queue(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        # Mock empty queue
        mock_redis.zrange.return_value = []
        
        result = manager.peek_next_task()
        
        assert result is None
    
    def test_claim_task_success(self, mock_redis, sample_task):
        manager = TaskManager(mock_redis)
        
        # Mock task exists in queue and Redis
        mock_redis.zscore.return_value = 1000  # Task exists in queue
        mock_redis.hget.return_value = sample_task.to_json()
        
        result = manager.claim_task(sample_task.task_id, 'worker-123')
        
        assert result.task_id == sample_task.task_id
        assert result.status == 'running'
        assert result.worker_id == 'worker-123'
        assert result.started is not None
        
        # Verify Redis operations
        mock_redis.zrem.assert_called_with('task_queue', sample_task.task_id)
        mock_redis.hset.assert_called()
    
    def test_claim_task_not_in_queue(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        # Mock task not in queue
        mock_redis.zscore.return_value = None
        
        result = manager.claim_task('nonexistent-task', 'worker-123')
        
        assert result is None
    
    def test_update_task_status_success(self, mock_redis, sample_task):
        manager = TaskManager(mock_redis)
        
        # Mock task exists
        mock_redis.hget.return_value = sample_task.to_json()
        
        result = manager.update_task_status(sample_task.task_id, 'completed', 'Success')
        
        assert result is True
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()
    
    def test_update_task_status_not_found(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        # Mock task doesn't exist
        mock_redis.hget.return_value = None
        
        result = manager.update_task_status('nonexistent-task', 'completed')
        
        assert result is False
    
    def test_get_tasks_no_filter(self, mock_redis, sample_task):
        manager = TaskManager(mock_redis)
        
        # Mock tasks in Redis
        mock_redis.hgetall.return_value = {
            sample_task.task_id: sample_task.to_json()
        }
        
        tasks, total = manager.get_tasks()
        
        assert len(tasks) == 1
        assert total == 1
        assert tasks[0].task_id == sample_task.task_id
    
    def test_get_tasks_with_filters(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Create multiple tasks
        task1 = TaskModel('ir_clouds', sample_timestamp, 'normal')
        task1.status = 'pending'
        
        task2 = TaskModel('true_color', sample_timestamp, 'high')
        task2.status = 'completed'
        
        # Mock tasks in Redis
        mock_redis.hgetall.return_value = {
            task1.task_id: task1.to_json(),
            task2.task_id: task2.to_json()
        }
        
        # Filter by status
        tasks, total = manager.get_tasks(status='pending')
        assert len(tasks) == 1
        assert tasks[0].status == 'pending'
        
        # Filter by composite
        tasks, total = manager.get_tasks(composite='true_color')
        assert len(tasks) == 1
        assert tasks[0].composite == 'true_color'
    
    def test_promote_tasks_in_queue(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Create tasks for promotion testing - use exact same timestamp for promotion
        promote_task = TaskModel('ir_clouds', sample_timestamp, 'normal')
        other_task = TaskModel('true_color', sample_timestamp.replace(hour=13), 'normal')
        
        # Mock queue with task IDs
        mock_redis.zrange.return_value = [promote_task.task_id, other_task.task_id]
        
        # Mock task retrieval - promote_task should be promoted, other_task should not
        def mock_hget(key, task_id):
            if task_id == promote_task.task_id:
                return promote_task.to_json()
            elif task_id == other_task.task_id:
                return other_task.to_json()
            return None
        
        mock_redis.hget.side_effect = mock_hget
        
        # Call promote tasks with same timestamp as promote_task
        manager.promote_tasks(sample_timestamp)
        
        # Verify that tasks were updated (hset called for promoted task)
        assert mock_redis.hset.call_count >= 1
        assert mock_redis.zadd.call_count >= 1
    
    def test_peek_next_task_deleted_task(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        # Mock task ID in queue but task doesn't exist in hash
        mock_redis.zrange.return_value = ['deleted-task-id']
        mock_redis.hget.return_value = None  # Task was deleted
        
        result = manager.peek_next_task()
        
        assert result is None
        # Verify task was removed from queue
        mock_redis.zrem.assert_called_with('task_queue', 'deleted-task-id')
    
    def test_peek_next_task_with_priority_filter(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Create tasks with different priorities
        high_task = TaskModel('ir_clouds', sample_timestamp, 'high')
        normal_task = TaskModel('true_color', sample_timestamp, 'normal')
        
        # Mock queue with both tasks
        mock_redis.zrange.return_value = [high_task.task_id, normal_task.task_id]
        
        # Mock task retrieval
        def mock_hget(key, task_id):
            if task_id == high_task.task_id:
                return high_task.to_json()
            elif task_id == normal_task.task_id:
                return normal_task.to_json()
            return None
        
        mock_redis.hget.side_effect = mock_hget
        
        # Filter by high priority only
        result = manager.peek_next_task(priorities=['high'])
        
        assert result.task_id == high_task.task_id
        assert result.priority == 'high'
    
    def test_peek_next_task_with_composite_filter(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Create tasks with different composites
        ir_task = TaskModel('ir_clouds', sample_timestamp, 'normal')
        tc_task = TaskModel('true_color', sample_timestamp, 'normal')
        
        # Mock queue with both tasks
        mock_redis.zrange.return_value = [ir_task.task_id, tc_task.task_id]
        
        # Mock task retrieval
        def mock_hget(key, task_id):
            if task_id == ir_task.task_id:
                return ir_task.to_json()
            elif task_id == tc_task.task_id:
                return tc_task.to_json()
            return None
        
        mock_redis.hget.side_effect = mock_hget
        
        # Filter by true_color composite only
        result = manager.peek_next_task(composites=['true_color'])
        
        assert result.task_id == tc_task.task_id
        assert result.composite == 'true_color'
    
    def test_peek_next_task_no_matching_filters(self, mock_redis, sample_timestamp):
        manager = TaskManager(mock_redis)
        
        # Create task with normal priority
        normal_task = TaskModel('ir_clouds', sample_timestamp, 'normal')
        
        # Mock queue with task
        mock_redis.zrange.return_value = [normal_task.task_id]
        mock_redis.hget.return_value = normal_task.to_json()
        
        # Filter by high priority only (should not match)
        result = manager.peek_next_task(priorities=['high'])
        
        assert result is None
    
    def test_claim_task_deleted_task(self, mock_redis):
        manager = TaskManager(mock_redis)
        
        # Mock task exists in queue but not in hash
        mock_redis.zscore.return_value = 1000  # Task exists in queue
        mock_redis.hget.return_value = None  # But task was deleted from hash
        
        result = manager.claim_task('deleted-task-id', 'worker-123')
        
        assert result is None
        # Verify task was removed from queue
        mock_redis.zrem.assert_called_with('task_queue', 'deleted-task-id')


class TestHimawariRawManager:
    """Test HimawariRawManager class"""
    
    def test_init(self, mock_redis):
        manager = HimawariRawManager(mock_redis)
        
        assert manager.redis == mock_redis
        assert manager.raws_key == 'himawari_raws'
        assert manager.timestamps_key == 'raws_timestamps'
        assert manager.expire_time == 3600 * 24 * 30
    
    def test_get_timestamp_key(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        result = manager._get_timestamp_key(sample_timestamp)
        
        assert result == '20250115_1200'
    
    def test_create_sync_new(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Mock sync doesn't exist
        mock_redis.hexists.return_value = False
        
        manager.create_sync(sample_timestamp)
        
        # Verify Redis calls
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()
        mock_redis.expire.assert_called()
    
    def test_create_sync_exists(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Mock sync already exists
        mock_redis.hexists.return_value = True
        
        manager.create_sync(sample_timestamp)
        
        # Should not create new sync
        mock_redis.hset.assert_not_called()
    
    def test_update_progress_existing(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Create existing raw
        existing_raw = HimawariRawModel(sample_timestamp)
        existing_raw.status = 'pending'
        
        # Mock existing raw in Redis
        mock_redis.hget.return_value = existing_raw.to_json()
        
        manager.update_progress(sample_timestamp, status='running', files=5, size=1024)
        
        # Verify Redis calls
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()
        mock_redis.expire.assert_called()
    
    def test_update_progress_new(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Mock no existing raw
        mock_redis.hget.return_value = None
        
        manager.update_progress(sample_timestamp, status='running')
        
        # Should create new raw and update it
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()
    
    def test_get_raw_exists(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Create sample raw
        raw = HimawariRawModel(sample_timestamp)
        raw.status = 'completed'
        raw.files = 10
        
        # Mock raw exists in Redis
        mock_redis.hget.return_value = raw.to_json()
        
        result = manager.get_raw(sample_timestamp)
        
        assert result['status'] == 'completed'
        assert result['files'] == 10
        assert result['timestamp'] == sample_timestamp
    
    def test_get_raw_not_exists(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Mock raw doesn't exist
        mock_redis.hget.return_value = None
        
        result = manager.get_raw(sample_timestamp)
        
        assert result is None
    
    def test_get_raws_with_pagination(self, mock_redis, sample_timestamp):
        manager = HimawariRawManager(mock_redis)
        
        # Mock total count
        mock_redis.zcard.return_value = 5
        
        # Mock timestamp keys
        mock_redis.zrevrange.return_value = ['20250115_1200', '20250115_1000']
        
        # Create sample raws
        raw1 = HimawariRawModel(sample_timestamp)
        raw2 = HimawariRawModel(sample_timestamp.replace(hour=10))
        
        # Mock raw data
        mock_redis.hget.side_effect = [raw1.to_json(), raw2.to_json()]
        
        results, total = manager.get_raws(limit=2, offset=0)
        
        assert total == 5
        assert len(results) == 2
        assert results[0]['timestamp'] == sample_timestamp
        
        # Verify Redis calls
        mock_redis.zcard.assert_called_with('raws_timestamps')
        mock_redis.zrevrange.assert_called_with('raws_timestamps', 0, 1)
    
    def test_update_progress_with_task_manager_promotion(self, mock_redis, sample_timestamp):
        # Create mock task manager
        mock_task_manager = Mock()
        manager = HimawariRawManager(mock_redis, mock_task_manager)
        
        # Create existing raw with pending status
        existing_raw = HimawariRawModel(sample_timestamp)
        existing_raw.status = 'pending'
        
        # Mock existing raw in Redis
        mock_redis.hget.return_value = existing_raw.to_json()
        
        # Update status to completed (should trigger task promotion)
        manager.update_progress(sample_timestamp, status='completed')
        
        # Verify task manager promotion was called
        mock_task_manager.promote_tasks.assert_called_once_with(sample_timestamp)
        
        # Verify Redis operations
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()
    
    def test_update_progress_no_task_manager(self, mock_redis, sample_timestamp):
        # Create manager without task manager
        manager = HimawariRawManager(mock_redis, task_manager=None)
        
        # Create existing raw
        existing_raw = HimawariRawModel(sample_timestamp)
        existing_raw.status = 'pending'
        
        # Mock existing raw in Redis
        mock_redis.hget.return_value = existing_raw.to_json()
        
        # Update status to completed (should not crash without task manager)
        manager.update_progress(sample_timestamp, status='completed')
        
        # Verify Redis operations still work
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()
