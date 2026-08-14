import json
import socket
import time

from flask import Blueprint, request

from backend.core.database import get_db
from backend.core.response import fail, ok


bp = Blueprint("intertime", __name__, url_prefix="/api/intertime")
DEFAULT = {"enabled": True, "nodes": ["www.baidu.com", "8.8.8.8:53"], "timeout": 2, "interval": 5, "display_names": {}}
SETTING_KEY = "intertime.config"


def _load():
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (SETTING_KEY,)).fetchone()
    if not row:
        return dict(DEFAULT)
    try:
        value = json.loads(row[0])
    except (TypeError, ValueError):
        return dict(DEFAULT)
    return {**DEFAULT, **value} if isinstance(value, dict) else dict(DEFAULT)


def _save(value):
    db = get_db()
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (SETTING_KEY, json.dumps(value, ensure_ascii=False)))
    db.commit()


def _target(node):
    if not isinstance(node, str) or not node.strip() or len(node) > 253:
        raise ValueError("节点格式非法")
    value = node.strip()
    if value.startswith("[") and "]:" in value:
        host, port = value[1:].split("]:", 1)
        return host, int(port)
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        if port.isdigit():
            return host, int(port)
    return value, 443


def _validate(data):
    nodes = data.get("nodes", DEFAULT["nodes"])
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 50:
        raise ValueError("nodes 必须是包含 1 到 50 个节点的数组")
    for node in nodes:
        host, port = _target(node)
        if not host or not 1 <= port <= 65535:
            raise ValueError("节点端口非法")
    timeout = data.get("timeout", DEFAULT["timeout"])
    interval = data.get("interval", DEFAULT["interval"])
    if not isinstance(timeout, (int, float)) or not 0.1 <= float(timeout) <= 30:
        raise ValueError("timeout 必须在 0.1 到 30 秒之间")
    if not isinstance(interval, (int, float)) or not 1 <= float(interval) <= 3600:
        raise ValueError("interval 必须在 1 到 3600 秒之间")
    names = data.get("display_names", {})
    if not isinstance(names, dict):
        raise ValueError("display_names 必须是对象")
    return {"enabled": bool(data.get("enabled", True)), "nodes": nodes, "timeout": float(timeout), "interval": float(interval), "display_names": names}


@bp.post("/get")
def get_config():
    return ok(_load())


@bp.post("/set")
def set_config():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    try:
        value = _validate({**_load(), **data})
    except ValueError as exc:
        return fail(400, str(exc))
    _save(value)
    return ok(value, "保存成功")


@bp.post("/test")
def test_nodes():
    data = request.get_json(silent=True) or {}
    config = {**_load(), **data}
    try:
        config = _validate(config)
    except ValueError as exc:
        return fail(400, str(exc))
    results = []
    for node in config["nodes"]:
        started = time.perf_counter()
        try:
            host, port = _target(node)
            with socket.create_connection((host, port), timeout=config["timeout"]):
                elapsed = round((time.perf_counter() - started) * 1000, 2)
            results.append({"node": node, "time_ms": elapsed, "ok": True})
        except (OSError, ValueError, OverflowError):
            results.append({"node": node, "time_ms": None, "ok": False})
    return ok({"results": results})


def _toggle(enabled):
    config = _load(); config["enabled"] = enabled; _save(config)
    return ok({"enabled": enabled})


@bp.post("/start")
def start(): return _toggle(True)


@bp.post("/stop")
def stop(): return _toggle(False)
