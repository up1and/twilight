"""
Tests for main views
"""
import json
from unittest.mock import patch, Mock


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
        response = client.get("/tiles/ir_clouds/invalid-timestamp/5/25/15.png")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid time format" in result["message"]


class TestTileJson:
    """Test tilejson endpoint"""
    
    def test_tilejson_invalid_composite(self, client):
        response = client.get("/tiles/invalid_composite/tile.json")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert 'not available' in result['message']
    
    @patch("rio_tiler.io.Reader")
    def test_tilejson_success_basic(self, mock_reader, client, app):
        # Setup mock for tilejson
        app.mock_minio.presigned_get_object.return_value = "http://mock-url"
        
        mock_cog = Mock()
        mock_reader.return_value.__enter__.return_value = mock_cog
        mock_cog.minzoom = 0
        mock_cog.maxzoom = 5
        mock_cog.get_geographic_bounds.return_value = [70, 0, 150, 55]
        
        response = client.get("/tiles/ir_clouds/tile.json")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert "tiles" in result
        assert "ir-clouds" in result["tiles"][0]


class TestNaturalEarthTile:
    """Test natural earth tile endpoint"""
    
    def test_invalid_zoom_level(self, client):
        response = client.get("/tiles/lands/25/0/0.pbf")  # Invalid zoom level
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "zoom level" in result["message"]
    
    def test_invalid_coordinates(self, client):
        response = client.get("/tiles/lands/5/100/100.pbf")  # Invalid coordinates for zoom 5
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "tile coordinates" in result["message"]
    
    @patch("server.views.main.os.path.exists")
    def test_mbtiles_not_found(self, mock_exists, client):
        mock_exists.return_value = False
        
        response = client.get("/tiles/lands/5/15/10.pbf")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert "mbtiles file not found" in result["message"]


class TestLatestCompositeState:
    """Test latest composite state endpoint"""
    
    def test_latest_composite_state(self, client):
        response = client.get('/api/composites/latest')
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert isinstance(result, dict)
        assert "ir_clouds" in result


class TestServeSnapshot:
    """Test snapshot serving endpoint"""
    
    def test_serve_snapshot_png(self, app, client):
        # Mock MinIO response
        mock_data = b"fake-image-data"
        mock_response = Mock()
        mock_response.read.return_value = mock_data
        app.mock_minio.get_object.return_value = mock_response
        
        response = client.get("/snapshots/test/image.png")
        
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert response.get_data() == mock_data
    
    def test_serve_snapshot_mp4(self, app, client):
        # Mock MinIO response
        mock_data = b"fake-video-data"
        mock_response = Mock()
        mock_response.read.return_value = mock_data
        app.mock_minio.get_object.return_value = mock_response
        
        response = client.get("/snapshots/test/video.mp4")
        
        assert response.status_code == 200
        assert response.mimetype == "video/mp4"
        assert response.get_data() == mock_data


class TestTileEndpoints:
    """Test all tile-related endpoints"""
    
    @patch("rio_tiler.io.Reader")
    def test_tile_endpoint_basic(self, mock_reader, app, client):
        # Setup mocks
        app.mock_minio.presigned_get_object.return_value = "http://mock-url"
        
        # Mock Reader instance
        mock_cog = Mock()
        mock_reader.return_value.__enter__.return_value = mock_cog
        
        # Mock the result of tile and render
        mock_img = Mock()
        mock_img.render.return_value = b"fake-png-data"
        # Mock img.data.shape[0]
        mock_img.data.shape = [3, 256, 256]
        mock_cog.tile.return_value = mock_img
        
        response = client.get("/tiles/ir_clouds/2025-01-15T12:00:00/5/15/10.png")
        
        assert response.status_code == 200
        assert response.get_data() == b"fake-png-data"
    
    def test_tile_invalid_composite(self, client):
        response = client.get("/tiles/non-existent/2025-01-15T12:00:00/5/15/10.png")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert "not available" in result["message"]
