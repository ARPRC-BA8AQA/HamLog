from flask import Blueprint, request, current_app
from backend.core.database import get_db
from backend.core.response import ok, fail
from backend.core.auth import issue_token, revoke_token, decode_token
from backend.core.security import issue_csrf
from backend.core.decorators import require_role

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
    response.set_cookie("hamlog_csrf", token, httponly=False, samesite="Lax", secure=request.is_secure)
    return response, status

@bp.post("/status")
def status():
    token = (request.headers.get("Authorization") or "").removeprefix("Bearer "); info = decode_token(token) if token else None
    auth_enabled = current_app.config["HAMLOG_CONFIG"]["auth"].get("enabled", False)
    setup_required = bool(auth_enabled and get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0)
    return ok({"auth_enabled": auth_enabled, "setup_required": setup_required, "logged_in": bool(info), "role": info.get("role") if info else None, "username": info.get("sub") if info else None})

@bp.post("/user/list")
@require_role("admin")
def user_list():
    rows = get_db().execute("SELECT id,username,role,created_at FROM users ORDER BY id").fetchall()
    return ok({"items": [dict(row) for row in rows]})

@bp.post("/user/create")
def user_create():
    data = request.get_json(silent=True) or {}; username = str(data.get("username", "")).strip(); password = data.get("password"); role = data.get("role", "user")
    if not username or not isinstance(password, str) or len(password) < 8: return fail(400, "用户名不能为空且密码至少 8 位")
    if role not in {"admin", "user"}: return fail(400, "role 必须是 admin 或 user")
    db = get_db(); user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count:
        from backend.core.decorators import authenticate_request, current_identity
        error = authenticate_request()
        if error: return error
        if current_identity().get("role") != "admin": return fail(403, "需要管理员权限")
    else:
        role = "admin"
    try:
        cursor = db.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)", (username, _hash(password), role)); db.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper(): return fail(409, "用户名已存在")
        raise
    return ok({"id": cursor.lastrowid, "username": username, "role": role}, "用户创建成功")

@bp.post("/user/update")
@require_role("admin")
def user_update():
    data = request.get_json(silent=True) or {}; user_id = data.get("id"); fields = [] ; values = []
    if "role" in data and data.get("role") not in {"admin", "user"}: return fail(400, "role 必须是 admin 或 user")
    if "password" in data and (not isinstance(data.get("password"), str) or len(data["password"]) < 8): return fail(400, "密码至少 8 位")
    db = get_db(); current = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if not current: return fail(404, "用户不存在")
    if data.get("role") == "user" and current["role"] == "admin" and db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] <= 1: return fail(409, "不能移除最后一个管理员")
    if data.get("role") in {"admin", "user"}: fields.append("role=?"); values.append(data["role"])
    if "password" in data: fields.append("password_hash=?"); values.append(_hash(data["password"]))
    if not fields: return fail(400, "没有可更新字段")
    cursor = db.execute(f"UPDATE users SET {','.join(fields)} WHERE id=?", values + [user_id]); db.commit()
    return ok({"id": user_id}, "用户更新成功")

@bp.post("/user/delete")
@require_role("admin")
def user_delete():
    user_id = (request.get_json(silent=True) or {}).get("id"); db = get_db(); user = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if not user: return fail(404, "用户不存在")
    if user["role"] == "admin" and db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] <= 1: return fail(409, "不能删除最后一个管理员")
    db.execute("DELETE FROM users WHERE id=?", (user_id,)); db.commit(); return ok(None, "用户删除成功")
