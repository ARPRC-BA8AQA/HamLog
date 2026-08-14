from flask import Blueprint, request, current_app
from backend.core.database import get_db
from backend.core.response import ok, fail
from backend.core.auth import issue_token, revoke_token, decode_token
from backend.core.security import issue_csrf

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
def _hash(password, salt=None):
    import hashlib
    import secrets
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"

def _valid(stored, password):
    import hashlib
    import hmac
    try: salt, digest = stored.split("$", 1)
    except ValueError: return False
    return hmac.compare_digest(_hash(password, salt).split("$", 1)[1], digest)

@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}; username, password = data.get("username"), data.get("password")
    if not username or not password: return fail(400, "用户名和密码不能为空")
    row = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not _valid(row["password_hash"], password): return fail(401, "用户名或密码错误")
    access = issue_token(username, row["role"]); refresh = issue_token(username, row["role"], "refresh")
    return ok({"access_token": access, "refresh_token": refresh, "expires_in": current_app.config["HAMLOG_CONFIG"]["auth"].get("access_token_expires", 7200), "role": row["role"], "username": username})

@bp.post("/refresh")
def refresh():
    token = (request.get_json(silent=True) or {}).get("refresh_token"); info = decode_token(token or "", expected_type="refresh")
    if not info: return fail(401, "refresh_token 无效或过期")
    access = issue_token(info["sub"], info["role"]); return ok({"access_token": access, "expires_in": current_app.config["HAMLOG_CONFIG"]["auth"].get("access_token_expires", 7200)})

@bp.post("/logout")
def logout():
    token = (request.headers.get("Authorization") or "").removeprefix("Bearer ")
    if token: revoke_token(token)
    return ok(None)

@bp.post("/csrf")
def csrf():
    token = issue_csrf()
    response, status = ok({"csrf_token": token})
    response.set_cookie("hamlog_csrf", token, httponly=False, samesite="Lax", secure=not current_app.config.get("TESTING", False))
    return response, status

@bp.post("/status")
def status():
    token = (request.headers.get("Authorization") or "").removeprefix("Bearer "); info = decode_token(token) if token else None
    return ok({"auth_enabled": current_app.config["HAMLOG_CONFIG"]["auth"].get("enabled", False), "logged_in": bool(info), "role": info.get("role") if info else None, "username": info.get("sub") if info else None})
