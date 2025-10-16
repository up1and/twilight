"""
Pytest configuration and fixtures
"""
import pytest
import datetime
from unittest.mock import Mock, patch
from server.app import create_app
from server.models import TaskModel, HimawariRawModel


@pytest.fixture
def app():
    """Create test app instance"""
    app = create_app()
    app.config["TESTING"] = True
    app.config["AVAILABLE_COMPOSITES"] = ["ir_clouds", "true_color", "ash", "night_microphysics"]
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    with app.app_context():
        yield app.test_client()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = Mock()
    # Mock common Redis operations
    redis_mock.hset.return_value = True
    redis_mock.hget.return_value = None
    redis_mock.hgetall.return_value = {}
    redis_mock.zadd.return_value = True
    redis_mock.zrange.return_value = []
    redis_mock.zrem.return_value = True
    redis_mock.expire.return_value = True
    redis_mock.lock.return_value.__enter__ = Mock(return_value=Mock())
    redis_mock.lock.return_value.__exit__ = Mock(return_value=None)
    return redis_mock


@pytest.fixture
def mock_minio():
    """Mock MinIO client"""
    minio_mock = Mock()
    minio_mock.presigned_get_object.return_value = "http://mock-url"
    minio_mock.get_object.return_value = Mock()
    minio_mock.list_objects.return_value = []
    return minio_mock


@pytest.fixture
def sample_timestamp():
    """Sample timestamp for testing"""
    return datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def sample_task(sample_timestamp):
    """Sample task for testing"""
    return TaskModel("ir_clouds", sample_timestamp, "normal")


@pytest.fixture
def sample_raw(sample_timestamp):
    """Sample raw for testing"""
    return HimawariRawModel(sample_timestamp)


@pytest.fixture
def mock_task_manager(mock_redis):
    """Mock TaskManager with Redis"""
    with patch("server.services.TaskManager") as mock_class:
        instance = mock_class.return_value
        instance.redis = mock_redis
        yield instance


@pytest.fixture
def mock_himawari_manager(mock_redis):
    """Mock HimawariRawManager with Redis"""
    with patch("server.services.HimawariRawManager") as mock_class:
        instance = mock_class.return_value
        instance.redis = mock_redis
        yield instance
