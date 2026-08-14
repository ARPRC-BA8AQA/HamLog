from flask import Blueprint, request
from backend.core.database import get_db
from backend.core.response import ok, fail

bp = Blueprint("settings", __name__, url_prefix="/api/settings")
SENSITIVE_KEYS = {"qrz_username_encrypted", "qrz_password_encrypted"}

def data():
    return request.get_json(silent=True) or {}

@bp.post("/get_all")
def get_all():
    rows = get_db().execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    return ok({row[0]: row[1] for row in rows if row[0] not in SENSITIVE_KEYS})

@bp.post("/get")
def get_one():
    key = data().get("key")
    if not isinstance(key, str) or not key: return fail(400, "key 不能为空")
    if key in SENSITIVE_KEYS: return fail(403, "敏感设置不能通过通用接口读取")
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return ok({"key": key, "value": row[0] if row else None})

@bp.post("/set")
def set_one():
    payload = data(); key, value = payload.get("key"), payload.get("value")
    if not isinstance(key, str) or not key or not isinstance(value, (str, int, float, bool, type(None))): return fail(400, "参数非法")
    if key in SENSITIVE_KEYS: return fail(403, "敏感设置不能通过通用接口修改")
    db = get_db(); db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value) if value is not None else "")); db.commit()
    return ok({"key": key, "value": value}, "设置成功")

@bp.post("/set_many")
def set_many():
    items = data().get("items")
    if not isinstance(items, dict): return fail(400, "items 必须是对象")
    if SENSITIVE_KEYS.intersection(items): return fail(403, "敏感设置不能通过通用接口修改")
    db = get_db()
    for key, value in items.items(): db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    db.commit(); return ok({"updated": list(items)})
