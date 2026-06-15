from functools import wraps

from flask import request, jsonify, current_app


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        challenges= {"WWW-Authenticate": 'Bearer realm="api"'}
        authorization = request.headers.get("Authorization", "")
        parts = authorization.split(None, 1)

        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "error": "Authentication Required",
                "message": "Please provide a Bearer token in the Authorization header."
            }), 401, challenges

        token = parts[1]
        if token != current_app.config.get("AUTH_KEY"):
            return jsonify({
                "error": "Invalid Token",
                "message": "The provided auth token is invalid. Please verify your credentials and try again."
            }), 401, challenges

        return f(*args, **kwargs)

    return decorated
