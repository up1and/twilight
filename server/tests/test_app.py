"""
Tests for Flask application
"""
from unittest.mock import Mock, patch
from server.app import create_app, add_cors_headers, add_cache_headers


class TestCreateApp:
    """Test Flask app creation"""
    
    @patch('server.app.initialize_composite_state')
    @patch('server.app.CompositeStateManager')
    @patch('server.app.HimawariRawManager')
    @patch('server.app.TaskManager')
    @patch('server.app.init_extensions')
    @patch('server.app.redis_client')
    @patch('server.app.client')
    def test_create_app(self, mock_client, mock_redis, mock_init_extensions, 
                       mock_task_manager_class, mock_himawari_manager_class, 
                       mock_composite_state_class, mock_initialize_state):
        # Mock the manager instances
        mock_task_manager = Mock()
        mock_himawari_manager = Mock()
        mock_composite_state = Mock()
        mock_composite_states = {"ir_clouds": None, "true_color": None}
        
        mock_task_manager_class.return_value = mock_task_manager
        mock_himawari_manager_class.return_value = mock_himawari_manager
        mock_composite_state_class.return_value = mock_composite_state
        mock_initialize_state.return_value = mock_composite_states
        
        app = create_app()
        
        assert app is not None
        assert app.config["AVAILABLE_COMPOSITES"] == [
            "ir_clouds", "true_color", "ash", "night_microphysics"
        ]
        
        # Verify extensions were initialized
        mock_init_extensions.assert_called_once_with(app)
        
        # Verify managers were created
        assert hasattr(app, "task_manager")
        assert hasattr(app, "himawari_raw_manager")
        assert hasattr(app, "composite_state")
        
        # Verify managers were initialized correctly
        mock_task_manager_class.assert_called_once_with(mock_redis)
        mock_himawari_manager_class.assert_called_once_with(mock_redis, mock_task_manager)
        mock_initialize_state.assert_called_once_with(mock_client, [
            "ir_clouds", "true_color", "ash", "night_microphysics"
        ])
        mock_composite_state_class.assert_called_once_with(mock_redis, mock_composite_states)
    
    @patch('server.app.initialize_composite_state')
    @patch('server.app.CompositeStateManager')
    @patch('server.app.HimawariRawManager')
    @patch('server.app.TaskManager')
    @patch('server.app.init_extensions')
    @patch('server.app.redis_client')
    @patch('server.app.client')
    def test_app_configuration(self, mock_client, mock_redis, mock_init_extensions,
                              mock_task_manager_class, mock_himawari_manager_class,
                              mock_composite_state_class, mock_initialize_state):
        """Test app configuration and JSON encoder"""
        mock_task_manager_class.return_value = Mock()
        mock_himawari_manager_class.return_value = Mock()
        mock_composite_state_class.return_value = Mock()
        mock_initialize_state.return_value = {}
        
        app = create_app()
        
        # Test JSON encoder is set
        assert app.json.default is not None
        
        # Test that blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        assert 'api' in blueprint_names
        assert 'main' in blueprint_names
    
    @patch('server.app.initialize_composite_state')
    @patch('server.app.CompositeStateManager')
    @patch('server.app.HimawariRawManager')
    @patch('server.app.TaskManager')
    @patch('server.app.init_extensions')
    @patch('server.app.redis_client')
    @patch('server.app.client')
    def test_error_handler_registration(self, mock_client, mock_redis, mock_init_extensions,
                                       mock_task_manager_class, mock_himawari_manager_class,
                                       mock_composite_state_class, mock_initialize_state):
        """Test that error handlers are registered"""
        mock_task_manager_class.return_value = Mock()
        mock_himawari_manager_class.return_value = Mock()
        mock_composite_state_class.return_value = Mock()
        mock_initialize_state.return_value = {}
        
        app = create_app()
        
        # Test that 500 error handler is registered
        assert 500 in app.error_handler_spec[None]
        
        # Test error handler functionality by triggering it
        with app.test_client() as client:
            # Create a route that will raise an exception
            @app.route("/test-error")
            def test_error():
                raise Exception("Test error")
            
            response = client.get("/test-error")
            
            assert response.status_code == 500
            data = response.get_json()
            assert data["error"] == "Internal Server Error"


class TestCorsHeaders:
    """Test CORS headers functionality"""
    
    def test_add_cors_headers(self):
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response()
        
        with app.app_context():
            result = add_cors_headers(response)
            
            assert result.headers['Access-Control-Allow-Origin'] == '*'
            assert 'GET, POST, PUT, DELETE' in result.headers['Access-Control-Allow-Methods']
            assert 'Content-Type, Authorization' in result.headers['Access-Control-Allow-Headers']


class TestCacheHeaders:
    """Test cache headers functionality"""
    
    def test_add_cache_headers_function_exists(self):
        """Test that add_cache_headers function exists and can be called"""
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response()
        
        # Test that the function can be called within request context
        with app.test_request_context("/test"):
            result = add_cache_headers(response)
            assert result is response  # Should return the same response object
    
    def test_add_cache_headers_tile_endpoint(self):
        """Test cache headers for tile endpoint"""
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response(mimetype="image/png")
        
        # Mock tile endpoint
        with app.test_request_context("/test"):
            with patch("server.app.request") as mock_request:
                mock_request.endpoint = "main.tile"
                result = add_cache_headers(response)
                
                assert 'Cache-Control' in result.headers
                assert result.headers['Cache-Control'] == 'public, max-age=43200'
                assert 'Expires' in result.headers
    
    def test_add_cache_headers_vector_tile_endpoint(self):
        """Test cache headers for natural earth tile endpoint"""
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response(mimetype="application/x-protobuf")
        
        # Mock natural earth tile endpoint
        with app.test_request_context("/test"):
            with patch("server.app.request") as mock_request:
                mock_request.endpoint = "main.vector_tile"
                result = add_cache_headers(response)
                
                assert 'Cache-Control' in result.headers
                assert result.headers['Cache-Control'] == 'public, max-age=43200'
                assert 'Expires' in result.headers
    
    def test_add_cache_headers_tilejson_endpoint(self):
        """Test cache headers for tilejson endpoint"""
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response(mimetype="application/json")
        
        # Mock tilejson endpoint
        with app.test_request_context("/test"):
            with patch("server.app.request") as mock_request:
                mock_request.endpoint = "main.tilejson"
                result = add_cache_headers(response)
                
                assert "Cache-Control" in result.headers
                assert result.headers["Cache-Control"] == "public, max-age=3600"
                assert "Expires" in result.headers


class TestAppHelperFunctions:
    """Test app helper functions"""
    
    def test_add_cors_headers(self):
        """Test CORS headers are added correctly"""
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response()
        
        with app.app_context():
            result = add_cors_headers(response)
            
            assert result.headers['Access-Control-Allow-Origin'] == '*'
            assert 'GET, POST, PUT, DELETE' in result.headers['Access-Control-Allow-Methods']
            assert 'Content-Type, Authorization' in result.headers['Access-Control-Allow-Headers']
    
    def test_add_cors_headers_function(self):
        """Test CORS headers function"""
        from flask import Flask, Response
        
        app = Flask(__name__)
        response = Response()
        
        with app.app_context():
            result = add_cors_headers(response)
            
            assert result.headers['Access-Control-Allow-Origin'] == '*'
            assert 'GET, POST, PUT, DELETE' in result.headers['Access-Control-Allow-Methods']
            assert 'Content-Type, Authorization' in result.headers['Access-Control-Allow-Headers']
    
    @patch("server.app.register_blueprints")
    @patch("server.app.initialize_composite_state")
    @patch("server.app.CompositeStateManager")
    @patch("server.app.HimawariRawManager")
    @patch("server.app.TaskManager")
    @patch("server.app.init_extensions")
    @patch("server.app.redis_client")
    @patch("server.app.client")
    def test_register_blueprints_called(self, mock_client, mock_redis, mock_init_extensions,
                                       mock_task_manager_class, mock_himawari_manager_class,
                                       mock_composite_state_class, mock_initialize_state, mock_register_blueprints):
        """Test that register_blueprints is called during app creation"""
        mock_task_manager_class.return_value = Mock()
        mock_himawari_manager_class.return_value = Mock()
        mock_composite_state_class.return_value = Mock()
        mock_initialize_state.return_value = {}
        
        app = create_app()
        
        mock_register_blueprints.assert_called_once_with(app)


class TestBlueprintRegistration:
    """Test blueprint registration"""
    
    def test_blueprints_registered(self):
        app = create_app()
        
        # Check that blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        assert 'api' in blueprint_names
        assert 'main' in blueprint_names
    
    def test_api_routes_exist(self):
        app = create_app()
        
        with app.test_client() as client:
            # Test that API routes are accessible
            response = client.get("/api/tasks")
            # Should not be 404 (route exists, even if it fails for other reasons)
            assert response.status_code != 404
    
    def test_main_routes_exist(self):
        app = create_app()
        
        with app.test_client() as client:
            # Test that main routes are accessible
            response = client.get("/")
            assert response.status_code == 200
