from pathlib import Path
from flask import Blueprint, current_app, request
from backend.core.response import ok, fail
from backend.plugins.auditor import audit
from backend.plugins.sandbox import invoke_plugin
from backend.core.database import get_db
import json
import re

bp = Blueprint("plugin", __name__, url_prefix="/api/plugin")

def root(): return Path(current_app.config.get("PLUGIN_DIR", Path(current_app.root_path).parent / "plugins"))

def plugin_path(plugin_id):
    if not isinstance(plugin_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,39}", plugin_id): return None
    return root() / plugin_id

def state(plugin_id):
    row = get_db().execute("SELECT enabled,sensitive_authorized FROM plugin_state WHERE id=?", (plugin_id,)).fetchone()
    return {"enabled": bool(row[0]) if row else False, "authorized": bool(row[1]) if row else False}

@bp.post("/installed")
def installed():
    items = []
    for path in root().iterdir() if root().exists() else []:
        if path.is_dir():
            good, errors = audit(path); status = state(path.name); items.append({"id": path.name, "audit_ok": good, "errors": errors, **status})
    return ok({"items": items})

@bp.post("/info")
def info():
    plugin_id = (request.get_json(silent=True) or {}).get("id"); path = plugin_path(plugin_id); manifest = path / "manifest.json" if path else None
    if not manifest or not manifest.exists(): return fail(404, "插件不存在")
    good, errors = audit(path); return ok({"manifest": json.loads(manifest.read_text(encoding="utf-8")), "audit_ok": good, "errors": errors, **state(plugin_id)})

@bp.post("/toggle")
def toggle():
    data = request.get_json(silent=True) or {}; plugin_id = data.get("id"); enabled = data.get("enabled"); path = plugin_path(plugin_id)
    if not path or not path.is_dir(): return fail(404, "插件不存在")
    good, errors = audit(path)
    if enabled and not good: return fail(422, "插件语法审核未通过,不允许加载", {"id": plugin_id, "audit_ok": False, "errors": errors})
    db = get_db(); db.execute("INSERT INTO plugin_state(id,enabled) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,updated_at=CURRENT_TIMESTAMP", (plugin_id, int(bool(enabled)))); db.commit()
    return ok({"id": plugin_id, "enabled": bool(enabled), "audit_ok": good})

@bp.post("/authorize")
def authorize():
    data = request.get_json(silent=True) or {}; plugin_id = data.get("id"); allowed = bool(data.get("allow_sensitive")); path = plugin_path(plugin_id)
    if not path or not path.is_dir(): return fail(404, "插件不存在")
    db = get_db(); db.execute("INSERT INTO plugin_state(id,sensitive_authorized) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET sensitive_authorized=excluded.sensitive_authorized,updated_at=CURRENT_TIMESTAMP", (plugin_id, int(allowed))); db.commit()
    return ok({"id": plugin_id, "authorized": allowed})

@bp.post("/invoke")
def invoke():
    data = request.get_json(silent=True) or {}; plugin_id = data.get("id"); action = data.get("action"); args = data.get("args", {}); path = plugin_path(plugin_id)
    if not path or not path.is_dir(): return fail(404, "插件不存在")
    status = state(plugin_id)
    if not status["enabled"]: return fail(422, "插件未启用")
    good, errors = audit(path)
    if not good: return fail(422, "插件语法审核未通过", {"errors": errors})
    if not isinstance(action, str) or not isinstance(args, dict): return fail(400, "action 或 args 参数非法")
    result = invoke_plugin(path, action, args, status["authorized"], current_app.config.get("PLUGIN_TIMEOUT", 30))
    if not result["ok"]: return fail(503, "插件运行异常", {"error": result["error"]})
    return ok({"result": result["result"], "ui": result.get("ui", {})})
