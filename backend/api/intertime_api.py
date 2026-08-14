import socket
import time
from flask import Blueprint, request
from backend.core.response import ok, fail

bp = Blueprint("intertime", __name__, url_prefix="/api/intertime")
DEFAULT = {"enabled": True, "nodes": ["www.baidu.com", "8.8.8.8"], "timeout": 2, "interval": 5, "display_names": {}}

@bp.post("/get")
def get_config(): return ok(DEFAULT)

@bp.post("/set")
def set_config():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("nodes", DEFAULT["nodes"]), list): return fail(400, "nodes 必须是数组")
    DEFAULT.update({key: data[key] for key in DEFAULT if key in data}); return ok(DEFAULT, "保存成功")

@bp.post("/test")
def test_nodes():
    data = request.get_json(silent=True) or {}; nodes = data.get("nodes", DEFAULT["nodes"]); timeout = float(data.get("timeout", DEFAULT["timeout"]))
    results = []
    for node in nodes:
        started = time.perf_counter()
        try:
            host = node if not str(node).count(":") else str(node).split(":", 1)[0]
            socket.getaddrinfo(host, 80, type=socket.SOCK_STREAM); results.append({"node": node, "time_ms": round((time.perf_counter() - started) * 1000, 2), "ok": True})
        except (OSError, ValueError): results.append({"node": node, "time_ms": None, "ok": False})
    return ok({"results": results})

@bp.post("/start")
def start(): DEFAULT["enabled"] = True; return ok({"enabled": True})

@bp.post("/stop")
def stop(): DEFAULT["enabled"] = False; return ok({"enabled": False})
