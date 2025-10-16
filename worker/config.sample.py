
endpoint = "127.0.0.1:9000"
access_key = "minioadmin"
secret_key = "minioadmin"

server_url = "http://127.0.0.1:5000"

# Task processor preferences
processing_profile = {
    # Priority filter: list of priorities, empty list means all priorities
    # Available priorities: "high", "normal", "low"
    "priorities": [],
    
    # Composite filter: list of composite names, empty list means all
    # Available composites: "ir_clouds", "true_color", "ash", "night_microphysics"
    "composites": []
}

# Cache management settings
# Maximum cache size in GB (default 200GB)
cache_size_limit = 200
