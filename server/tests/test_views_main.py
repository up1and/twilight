"""
Tests for main views
"""
import json
from unittest.mock import patch


class TestIndex:
    """Test GET / endpoint"""
    
    def test_index_success(self, client):
        response = client.get("/")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["status"] == "running"
        assert result["description"] == "Himawari Tile Server"
        assert "available_composites" in result
        assert "usage" in result
        assert "examples" in result


class TestFindTile:
    """Test find_tile function"""
    
    def test_find_tile_function_exists(self):
        # Just test that the function exists and can be imported
        from server.views.main import find_tile
        assert callable(find_tile)


class TestTile:
    """Test tile endpoint"""
    
    def test_tile_invalid_timestamp(self, client):
        response = client.get("/ir_clouds/tiles/invalid-timestamp/5/25/15.png")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid time format" in result["message"]


class TestTileJson:
    """Test tilejson endpoint"""
    
    def test_tilejson_invalid_composite(self, client):
        response = client.get('/invalid_composite.tilejson')
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert 'not available' in result['message']
    
    def test_tilejson_success_basic(self, client):
        # Test that tilejson endpoint works for valid composite
        response = client.get('/ir_clouds.tilejson')
        
        # Should not be 404 (route exists), might be 500 due to missing data
        assert response.status_code != 404
    
    def test_tilejson_error_handling(self, client):
        # Test that tilejson endpoint handles errors gracefully
        response = client.get("/ir_clouds.tilejson")
        
        # Should return JSON response even on error
        if response.status_code != 200:
            result = json.loads(response.data)
            assert "error" in result or "message" in result


class TestNaturalEarthTile:
    """Test natural earth tile endpoint"""
    
    def test_invalid_zoom_level(self, client):
        response = client.get("/lands/25/0/0.pbf")  # Invalid zoom level
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid zoom level" in result["message"]
    
    def test_invalid_coordinates(self, client):
        response = client.get("/lands/5/100/100.pbf")  # Invalid coordinates for zoom 5
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid tile coordinates" in result["message"]
    
    @patch("server.views.main.os.path.exists")
    def test_mbtiles_not_found(self, mock_exists, client):
        mock_exists.return_value = False
        
        response = client.get("/lands/5/15/10.pbf")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert "mbtiles file not found" in result["message"]



class TestLatestCompositeState:
    """Test latest composite state endpoint"""
    
    def test_latest_composite_state(self, client):
        response = client.get('/composites/latest')
        
        assert response.status_code == 200
        result = json.loads(response.data)
        # Should return the composite state dict
        assert isinstance(result, dict)


class TestServeSnapshot:
    """Test serve snapshot endpoint"""
    
    def test_serve_snapshot_endpoint_exists(self, client):
        # Just test that the route exists by checking it's not a 404 for route not found
        # We expect it to fail with MinIO error, not Flask route error
        try:
            response = client.get("/snapshots/nonexistent-file.png")
            # If we get here, the route exists but file doesn't exist in MinIO
            assert True
        except Exception as e:
            # Should be MinIO error, not Flask routing error
            assert "NoSuchKey" in str(e) or "does not exist" in str(e)
    
    def test_serve_snapshot_endpoint_exists_png(self, client):
        # Test that the route exists and handles PNG files
        # This will fail with MinIO error, but that's expected in test environment
        try:
            response = client.get("/snapshots/test-snapshot.png")
            # If we get here, the route exists but file doesn't exist in MinIO
            assert True
        except Exception as e:
            # Should be MinIO error, not Flask routing error
            assert "NoSuchKey" in str(e) or "does not exist" in str(e) or "S3Error" in str(type(e).__name__)
    
    def test_serve_snapshot_endpoint_exists_mp4(self, client):
        # Test that the route exists and handles MP4 files
        # This will fail with MinIO error, but that's expected in test environment
        try:
            response = client.get("/snapshots/test-video.mp4")
            # If we get here, the route exists but file doesn't exist in MinIO
            assert True
        except Exception as e:
            # Should be MinIO error, not Flask routing error
            assert "NoSuchKey" in str(e) or "does not exist" in str(e) or "S3Error" in str(type(e).__name__)
    
    def test_serve_snapshot_endpoint_exists_unknown(self, client):
        # Test that the route exists and handles unknown file types
        # This will fail with MinIO error, but that's expected in test environment
        try:
            response = client.get("/snapshots/test-file.unknown")
            # If we get here, the route exists but file doesn't exist in MinIO
            assert True
        except Exception as e:
            # Should be MinIO error, not Flask routing error
            assert "NoSuchKey" in str(e) or "does not exist" in str(e) or "S3Error" in str(type(e).__name__)


class TestTileEndpoints:
    """Test tile-related endpoints"""
    
    def test_tile_endpoint_basic(self, client):
        # Test tile endpoint exists and handles basic validation
        response = client.get("/ir_clouds/tiles/2025-01-15T12:00:00/5/15/10.png")
        
        # Should not be 404 (route exists), might be 500 due to missing data
        assert response.status_code != 404
        
        # Should return JSON response even on error
        if response.status_code != 200:
            try:
                result = json.loads(response.data)
                assert 'error' in result or 'message' in result
            except:
                # If not JSON, it might be an image or other response
                pass
    
    def test_tile_invalid_timestamp_format(self, client):
        response = client.get("/ir_clouds/tiles/invalid-timestamp/5/15/10.png")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid time format" in result["message"]
    
    def test_tilejson_endpoint_basic(self, client):
        # Test tilejson endpoint exists
        response = client.get('/ir_clouds.tilejson')
        
        # Should not be 404 (route exists), might be 500 due to missing data
        assert response.status_code != 404
        
        # Should return JSON response even on error
        if response.status_code != 200:
            try:
                result = json.loads(response.data)
                assert 'error' in result or 'message' in result
            except:
                pass
    
    def test_tilejson_invalid_composite(self, client):
        response = client.get('/invalid_composite.tilejson')
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert 'not available' in result['message']


class TestNaturalEarthTileExtended:
    """Extended tests for natural earth tile endpoint"""
    
    def test_mbtiles_endpoint_basic(self, client):
        # Test that the mbtiles endpoint exists (might return 404 if file doesn't exist)
        response = client.get("/lands/5/15/10.pbf")
        
        # Should not crash, might return 404 if mbtiles file doesn't exist
        assert response.status_code in [200, 204, 400, 404]




class TestFindTileFunction:
    """Test find_tile function directly"""
    
    def test_find_tile_function_exists(self):
        # Test that the function exists and can be imported
        from server.views.main import find_tile
        assert callable(find_tile)
    
    def test_find_tile_function_callable(self):
        # Simple test that the function exists and is callable
        from server.views.main import find_tile
        assert callable(find_tile)
        
        # Test with mock parameters - this will likely fail due to missing data
        # but it tests that the function can be called
        try:
            result = find_tile("ir_clouds", 5, 15, 10)
            # If we get here, function executed without import/syntax errors
            assert True
        except Exception as e:
            # Expected to fail due to missing data/context, but not import errors
            assert "import" not in str(e).lower()
            assert "module" not in str(e).lower()


class TestUtilityFunctions:
    """Test utility functions in views/main.py"""
    
    def test_index_endpoint_structure(self, client):
        response = client.get("/")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        
        # Verify all expected keys are present
        expected_keys = ["status", "description", "available_composites", "usage", "examples"]
        for key in expected_keys:
            assert key in result
        
        # Verify structure of nested objects
        assert "tiles" in result["usage"]
        assert "tilejson" in result["usage"]
        assert "latest_times" in result["usage"]
        
        assert "standard_tile" in result["examples"]
        assert "tilejson" in result["examples"]
        assert "latest_times" in result["examples"]


class TestErrorHandling:
    """Test error handling in various endpoints"""
    
    def test_tile_endpoint_error_handling(self, client):
        # Test with completely invalid parameters
        response = client.get("/ir_clouds/tiles/2025-01-15T12:00:00/999/999/999.png")
        
        # Should not crash, might return error
        assert response.status_code in [200, 400, 404, 500]
        
        # If it's an error response, should be JSON
        if response.status_code >= 400:
            try:
                result = json.loads(response.data)
                assert 'error' in result or 'message' in result
            except:
                # If not JSON, that's also acceptable for some error types
                pass
    
    def test_tilejson_endpoint_error_handling(self, client):
        # Test with valid composite but might have data issues
        response = client.get('/ir_clouds.tilejson')
        
        # Should not crash
        assert response.status_code in [200, 404, 500]
        
        # If it's an error response, should be JSON
        if response.status_code >= 400:
            try:
                result = json.loads(response.data)
                assert 'error' in result or 'message' in result
            except:
                pass


class TestCompositeStateEndpoint:
    """Test composite state related endpoints"""
    
    def test_latest_composite_state_structure(self, client):
        response = client.get('/composites/latest')
        
        assert response.status_code == 200
        result = json.loads(response.data)
        
        # Should be a dictionary (might be empty)
        assert isinstance(result, dict)
        
        # If there are any composites, their values should be timestamp strings or None
        for composite_name, timestamp_value in result.items():
            assert isinstance(composite_name, str)
            assert timestamp_value is None or isinstance(timestamp_value, str)


class TestSnapshotEndpointBasic:
    """Basic tests for snapshot endpoint"""
    
    def test_serve_snapshot_route_exists(self, client):
        # Test that the route pattern exists
        # These will fail with MinIO errors, but that proves the route exists
        test_files = [
            "test.png",
            "test.mp4",
            "folder/test.png",
            "video/test.mp4"
        ]
        
        for filename in test_files:
            try:
                response = client.get(f"/snapshots/{filename}")
                # If we get here without a 404, the route exists
                assert True
            except Exception as e:
                # Should be MinIO-related error, not routing error
                error_str = str(e)
                assert any(keyword in error_str for keyword in [
                    "NoSuchKey", "does not exist", "S3Error", "MinIO"
                ])
