import platform
import os
import sys
import time
from datetime import datetime, timezone
from flask import Blueprint, current_app, request
from backend.core.database import get_db, schema_status
from backend.core.response import ok, fail
from backend.core.crypto import get_crypto
from backend.core.time_sync import TimeSyncService, TimeSyncUnavailable
from backend.services.backup_service import BackupError, create_backup
from backend.config import save_config
from backend.core.decorators import require_role

bp = Blueprint("system", __name__, url_prefix="/api/system")

@bp.post("/info")
def info():
    started_at = current_app.extensions.setdefault("started_at", time.monotonic())
    return ok({"app_version": "Release 2.0.0", "python_version": sys.version.split()[0], "platform": platform.platform(), "db_path": current_app.config["DB_PATH"], "uptime_seconds": max(0, int(time.monotonic() - started_at))})

@bp.post("/db_status")
def db_status(): return ok(schema_status())

@bp.post("/sync_status")
def sync_status():
    config = current_app.config["HAMLOG_CONFIG"].get("time_sync", {})
    state = current_app.extensions.setdefault("time_sync_state", {"last_sync": None, "offset_ms": None})
    return ok({**state, "auto_elevate": bool(config.get("auto_elevate", True))})


@bp.post("/sync_time")
@require_role("admin")
def sync_time():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    config = current_app.config["HAMLOG_CONFIG"].get("time_sync", {})
    servers = data.get("servers", config.get("servers", list(TimeSyncService.DEFAULT_SERVERS)))
    if not isinstance(servers, list) or not servers:
        return fail(400, "servers 必须是非空数组")
    service = current_app.config.get("TIME_SYNC_SERVICE")
    if service is None:
        service = current_app.extensions.setdefault("time_sync_service", TimeSyncService())
    try:
        result = service.sync(
            servers,
            timeout=config.get("timeout", 2),
            auto_elevate=config.get("auto_elevate", True),
        )
    except ValueError as exc:
        return fail(400, str(exc))
    except TimeSyncUnavailable as exc:
        return fail(503, str(exc))
    current_app.extensions["time_sync_state"] = {
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "offset_ms": result["offset_ms"],
    }
    return ok(result)

@bp.post("/aes_status")
def aes_status():
    config = current_app.config["HAMLOG_CONFIG"].setdefault("security", {})
    return ok({"enabled": bool(config.get("aes_enabled", False)), "has_key": bool(os.environ.get("HAMLOG_AES_KEY") or os.environ.get("HAMLOG_AES_KEY_B64"))})

@bp.post("/aes_enable")
@require_role("admin")
def aes_enable():
    try: get_crypto(current_app._get_current_object())
    except ValueError as exc: return fail(503, str(exc))
    current_app.config["HAMLOG_CONFIG"].setdefault("security", {})["aes_enabled"] = True
    if not current_app.config.get("TESTING"):
        save_config(current_app.config["HAMLOG_CONFIG"], current_app.config.get("CONFIG_PATH"))
    return ok({"enabled": True, "migrated_fields": 0})

@bp.post("/aes_disable")
@require_role("admin")
def aes_disable():
    current_app.config["HAMLOG_CONFIG"].setdefault("security", {})["aes_enabled"] = False
    if not current_app.config.get("TESTING"):
        save_config(current_app.config["HAMLOG_CONFIG"], current_app.config.get("CONFIG_PATH"))
    return ok({"enabled": False, "migrated_fields": 0})

@bp.post("/log/query")
@require_role("admin")
def log_query():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    level = data.get("level")
    keyword = data.get("keyword")
    source = data.get("source")
    if level is not None:
        if not isinstance(level, str) or level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return fail(400, "level 非法")
        level = level.upper()
    if keyword is not None and not isinstance(keyword, str):
        return fail(400, "keyword 必须是字符串或 null")
    if source is not None and not isinstance(source, str):
        return fail(400, "source 必须是字符串或 null")
    limit = data.get("limit", 500)
    offset = data.get("offset", 0)
    if not isinstance(limit, int) or isinstance(limit, bool) or not isinstance(offset, int) or isinstance(offset, bool):
        return fail(400, "limit 和 offset 必须是整数")
    if not 1 <= limit <= 1000 or offset < 0:
        return fail(400, "limit 必须是 1 到 1000，offset 不能小于 0")

    clauses = []
    params = []
    if level:
        clauses.append("level = ?")
        params.append(level)
    if keyword:
        clauses.append("message LIKE ?")
        params.append(f"%{keyword}%")
    if source:
        clauses.append("source = ?")
        params.append(source)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM app_logs" + where, params).fetchone()[0]
    rows = db.execute(
        "SELECT id,timestamp,level,source,message FROM app_logs" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return ok({"total": total, "items": [dict(row) for row in rows]})


@bp.post("/log/stats")
@require_role("admin")
def log_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM app_logs").fetchone()[0]
    rows = db.execute("SELECT level,COUNT(*) AS count FROM app_logs GROUP BY level").fetchall()
    by_level = {level: 0 for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")}
    for row in rows:
        if row["level"] in by_level:
            by_level[row["level"]] = row["count"]
    return ok({"total": total, "by_level": by_level})


@bp.post("/backup")
@require_role("admin")
def backup():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    keep_count = data.get("keep_count", 10)
    if not isinstance(keep_count, int) or isinstance(keep_count, bool):
        return fail(400, "keep_count 必须是整数")
    try:
        result = create_backup(current_app.config["DATA_DIR"], current_app.config["DB_PATH"], keep_count, current_app.config.get("CONFIG_PATH"), current_app.config.get("PLUGIN_DIR"))
    except ValueError as exc:
        return fail(400, str(exc))
    except BackupError as exc:
        return fail(500, str(exc))
    return ok(result)
