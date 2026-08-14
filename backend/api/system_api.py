import platform
import os
import sys
from flask import Blueprint, current_app, request
from backend.core.response import ok, fail
from backend.core.crypto import get_crypto

bp = Blueprint("system", __name__, url_prefix="/api/system")

@bp.post("/info")
def info():
    return ok({"app_version": "Release 2.0.0", "python_version": sys.version.split()[0], "platform": platform.platform(), "db_path": current_app.config["DB_PATH"]})

@bp.post("/db_status")
def db_status(): return ok({"schema_version": "1.0", "pending_migrations": 0})

@bp.post("/sync_status")
def sync_status(): return ok({"last_sync": None, "offset_ms": None, "auto_elevate": current_app.config["HAMLOG_CONFIG"]["time_sync"].get("auto_elevate", False) if "time_sync" in current_app.config["HAMLOG_CONFIG"] else False})

@bp.post("/aes_status")
def aes_status():
    config = current_app.config["HAMLOG_CONFIG"].setdefault("security", {})
    return ok({"enabled": bool(config.get("aes_enabled", False)), "has_key": bool(os.environ.get("HAMLOG_AES_KEY") or os.environ.get("HAMLOG_AES_KEY_B64"))})

@bp.post("/aes_enable")
def aes_enable():
    try: get_crypto(current_app._get_current_object())
    except ValueError as exc: return fail(503, str(exc))
    current_app.config["HAMLOG_CONFIG"].setdefault("security", {})["aes_enabled"] = True
    return ok({"enabled": True, "migrated_fields": 0})

@bp.post("/aes_disable")
def aes_disable():
    current_app.config["HAMLOG_CONFIG"].setdefault("security", {})["aes_enabled"] = False
    return ok({"enabled": False, "migrated_fields": 0})

@bp.post("/encrypt_test")
def encrypt_test():
    if not current_app.config["HAMLOG_CONFIG"].get("security", {}).get("aes_enabled", False):
        return fail(400, "AES 加密未开启")
    value = (request.get_json(silent=True) or {}).get("value")
    if not isinstance(value, str): return fail(400, "value 必须是字符串")
    crypto = get_crypto(current_app._get_current_object()); token = crypto.encrypt(value)
    return ok({"ciphertext": token, "plaintext": crypto.decrypt(token)})
