from pathlib import Path
from flask import Blueprint, current_app, request
from backend.core.response import ok, fail
from backend.plugins.auditor import audit

bp = Blueprint("plugin", __name__, url_prefix="/api/plugin")

def root(): return Path(current_app.config.get("PLUGIN_DIR", Path(current_app.root_path).parent / "plugins"))

@bp.post("/installed")
def installed():
    items = []
    for path in root().iterdir() if root().exists() else []:
        if path.is_dir():
            good, errors = audit(path); items.append({"id": path.name, "audit_ok": good, "errors": errors, "enabled": good})
    return ok({"items": items})

@bp.post("/info")
def info():
    plugin_id = (request.get_json(silent=True) or {}).get("id"); path = root() / str(plugin_id); manifest = path / "manifest.json"
    if not manifest.exists(): return fail(404, "插件不存在")
    import json
    good, errors = audit(path); return ok({"manifest": json.loads(manifest.read_text(encoding="utf-8")), "audit_ok": good, "errors": errors, "enabled": good})
