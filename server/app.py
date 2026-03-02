"""
Main Flask application entry point
"""
import logging
import datetime

from flask import Flask, request, jsonify

from extensions import init_extensions, redis_client, client
from services import TaskManager, SyncManager, CompositeStateManager
from utils import default_json_handler, initialize_composite_state


available_composites = [
    "ir_clouds", "true_color", "ash", "night_microphysics"
]

def add_cors_headers(response):
    """Add CORS headers and cache control"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

def add_cache_headers(response):
    # Add HTTP cache headers for tile and tilejson responses
    if request.endpoint == "main.tile" and response.mimetype == "image/png" or \
        request.endpoint == "main.vector_tile" and response.mimetype == "application/x-protobuf":
        # Cache pbf tiles for 12 hours (43200 seconds)
        response.headers["Cache-Control"] = "public, max-age=43200"
        response.headers["Expires"] = (datetime.datetime.now(datetime.timezone.utc) +
                                        datetime.timedelta(hours=12)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    elif request.endpoint == "main.tilejson" and response.mimetype == "application/json":
        # Cache tilejson for 1 hour (3600 seconds)
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["Expires"] = (datetime.datetime.now(datetime.timezone.utc) +
                                        datetime.timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    return response

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    from views import api, main
    app.register_blueprint(api)
    app.register_blueprint(main)

def create_app():
    """Create and configure Flask application"""
    # Create Flask app
    app = Flask(__name__)
    app.config["AVAILABLE_COMPOSITES"] = available_composites

    # Initialize extensions
    init_extensions(app)
    app.client = client

    # Register blueprints
    register_blueprints(app)

    # Configure JSON encoder
    app.json.default = default_json_handler

    # Initialize managers and composite state
    app.task_manager = TaskManager(redis_client)
    app.sync_manager = SyncManager(redis_client, app.task_manager)

    composite_states = initialize_composite_state(client, available_composites)
    app.composite_state = CompositeStateManager(redis_client, composite_states)

    app.after_request(add_cors_headers)
    app.after_request(add_cache_headers)

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error"""
        app.logger.error(f"Internal Server Error: {error}", exc_info=True)
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }), 500
    
    if not app.debug:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(module)s - %(levelname)s: %(message)s"))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
