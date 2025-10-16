"""
Tests for extensions module
"""
from server.extensions import init_extensions, redis_client, client, cache


class TestExtensions:
    """Test extensions initialization and configuration"""
    
    def test_init_extensions(self):
        """Test that extensions initialization function exists and can be called"""
        from flask import Flask
        
        app = Flask(__name__)
        
        # Test that init_extensions can be called without error
        # (The actual initialization happens at module import time)
        try:
            init_extensions(app)
            # If we get here, the function executed successfully
            assert True
        except Exception as e:
            # If there's an error, the test should fail
            assert False, f"init_extensions failed: {e}"
    
    def test_redis_client_exists(self):
        """Test that redis_client is available"""
        assert redis_client is not None
    
    def test_minio_client_exists(self):
        """Test that minio client is available"""
        assert client is not None
    
    def test_cache_exists(self):
        """Test that cache is available"""
        assert cache is not None
    
    def test_redis_client_type(self):
        """Test Redis client type"""
        # Test that redis_client has expected attributes
        assert hasattr(redis_client, "get")
        assert hasattr(redis_client, "set")
        assert hasattr(redis_client, "hget")
        assert hasattr(redis_client, "hset")
    
    def test_minio_client_type(self):
        """Test MinIO client type"""
        # Test that client has expected attributes
        assert hasattr(client, "get_object")
        assert hasattr(client, "put_object")
        assert hasattr(client, "list_objects")
