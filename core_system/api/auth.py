# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | API AUTHENTICATION
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
API Authentication Middleware.
Bearer token validation for all operational endpoints.
"""

from functools import wraps
from flask import request, jsonify

from config import API_KEY


def require_auth(f):
    """Decorator to enforce Bearer token authentication on Flask routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 403
        return f(*args, **kwargs)
    return decorated