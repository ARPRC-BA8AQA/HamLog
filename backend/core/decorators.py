from functools import wraps
from flask import current_app, g, request
from backend.core.auth import decode_token
from backend.core.response import fail


def authenticate_request():
    """Authenticate an API request once before its view is called."""
    auth = current_app.config["HAMLOG_CONFIG"].get("auth", {})
    if not auth.get("enabled", False):
        g.current_user = {"sub": "admin", "role": "admin", "anonymous": True}
        return None
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return fail(401, "未认证或 Token 已过期")
    payload = decode_token(header[7:].strip())
    if not payload:
        return fail(401, "未认证或 Token 已过期")
    g.current_user = payload
    return None


def current_identity():
    return getattr(g, "current_user", {"sub": "admin", "role": "admin"})


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        error = authenticate_request()
        if error:
            return error
        return view(*args, **kwargs)
    return wrapped


def require_role(role):
    def decorator(view):
        @wraps(view)
        @require_auth
        def wrapped(*args, **kwargs):
            if current_identity().get("role") != role:
                return fail(403, f"需要 {role} 权限")
            return view(*args, **kwargs)
        return wrapped
    return decorator
