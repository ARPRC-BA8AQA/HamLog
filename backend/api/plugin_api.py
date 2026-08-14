import json
import re
import threading
from pathlib import Path

from flask import Blueprint, current_app, request

from backend.core.database import get_db
from backend.core.response import fail, ok
from backend.core.decorators import require_role
from backend.plugins.auditor import audit
from backend.plugins.sandbox import invoke_plugin
from backend.plugins.sources import (
    OFFICIAL_SOURCE_ID,
    SourceError,
    add_source,
    build_market,
    cached_items,
    ensure_official_source,
    find_cached_item,
    install_plugin,
    is_newer,
    list_sources,
    refresh_sources,
    remove_plugin,
    semver_installed_version,
    state,
    valid_plugin_id,
)


bp = Blueprint("plugin", __name__, url_prefix="/api/plugin")


def root():
    return Path(current_app.config.get("PLUGIN_DIR", Path(current_app.root_path).parent / "plugins"))


def plugin_path(plugin_id):
    if not valid_plugin_id(plugin_id):
        return None
    return root() / plugin_id


def payload():
    return request.get_json(silent=True) or {}


def source_failure(exc):
    return fail(exc.code, str(exc), exc.data)


def read_manifest(path):
    try:
        value = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def cached_metadata(db, plugin_id, source_id=None):
    entry = find_cached_item(db, plugin_id, source_id)
    if not entry:
        return {
            "source_id": source_id,
            "source_type": None,
            "rating": None,
            "author_rating": None,
            "verified": False,
            "badges": [],
        }
    item = entry["item"]
    official = entry["source_type"] == "official"
    return {
        "source_id": entry["source_id"],
        "source_type": entry["source_type"],
        "rating": item.get("rating"),
        "author_rating": item.get("author_rating"),
        "verified": bool(item.get("verified", False)) if official else False,
        "badges": item.get("badges") or [],
    }


def installed_item(db, path):
    manifest = read_manifest(path) or {"id": path.name, "name": path.name}
    good, errors = audit(path)
    status = state(db, path.name)
    metadata = cached_metadata(db, path.name, status["source_id"])
    sensitive = manifest.get("sensitive_permissions") or []
    return {
        "id": path.name,
        "name": manifest.get("name", path.name),
        "version": manifest.get("version"),
        "enabled": status["enabled"],
        "audit_ok": good,
        "errors": errors,
        "permissions": manifest.get("permissions") or [],
        "sensitive_permissions": sensitive,
        "authorized": not sensitive or status["authorized"],
        **metadata,
    }


@bp.post("/source/list")
def source_list():
    return ok({"sources": list_sources(get_db())})


@bp.post("/source/add")
@require_role("admin")
def source_add():
    data = payload()
    try:
        source = add_source(get_db(), data.get("name"), data.get("url"), current_app.config)
    except SourceError as exc:
        return source_failure(exc)
    return ok(source, "插件源添加成功")


@bp.post("/source/delete")
@require_role("admin")
def source_delete():
    source_id = payload().get("id")
    if source_id == OFFICIAL_SOURCE_ID:
        return fail(403, "官方插件源不可删除")
    if not isinstance(source_id, str) or not source_id:
        return fail(400, "id 不能为空")
    db = get_db()
    row = db.execute("SELECT id FROM plugin_sources WHERE id=?", (source_id,)).fetchone()
    if not row:
        return fail(404, "插件源不存在")
    installed = db.execute("SELECT id FROM plugin_state WHERE source_id=?", (source_id,)).fetchall()
    if installed:
        return fail(409, "插件源仍有关联的已安装插件", {"plugins": [row["id"] for row in installed]})
    db.execute("DELETE FROM plugin_market_cache WHERE source_id=?", (source_id,))
    db.execute("DELETE FROM plugin_sources WHERE id=?", (source_id,))
    db.commit()
    return ok(None, "删除成功")


@bp.post("/source/toggle")
@require_role("admin")
def source_toggle():
    data = payload()
    source_id = data.get("id")
    enabled = data.get("enabled")
    if not isinstance(source_id, str) or not source_id or not isinstance(enabled, bool):
        return fail(400, "id 或 enabled 参数非法")
    ensure_official_source(get_db())
    db = get_db()
    cursor = db.execute("UPDATE plugin_sources SET enabled=? WHERE id=?", (int(enabled), source_id))
    db.commit()
    if not cursor.rowcount:
        return fail(404, "插件源不存在")
    return ok({"id": source_id, "enabled": enabled})


@bp.post("/source/refresh")
@require_role("admin")
def source_refresh():
    source_id = payload().get("source_id")
    if source_id is not None and (not isinstance(source_id, str) or not source_id):
        return fail(400, "source_id 参数非法")
    try:
        result = refresh_sources(get_db(), current_app.config, source_id)
    except SourceError as exc:
        return source_failure(exc)
    return ok(result)


@bp.post("/market")
def market():
    data = payload()
    source_id = data.get("source_id")
    keyword = data.get("keyword")
    sort = data.get("sort", "rating")
    if source_id is not None and (not isinstance(source_id, str) or not source_id):
        return fail(400, "source_id 参数非法")
    if keyword is not None and not isinstance(keyword, str):
        return fail(400, "keyword 参数非法")
    if sort not in {"rating", "updated", "name"}:
        return fail(400, "sort 参数非法")
    db = get_db()
    ensure_official_source(db)
    if source_id and not db.execute("SELECT 1 FROM plugin_sources WHERE id=?", (source_id,)).fetchone():
        return fail(404, "插件源不存在")
    # Ensure a first market visit establishes an offline-capable official cache.
    if not db.execute("SELECT 1 FROM plugin_market_cache LIMIT 1").fetchone():
        try:
            refresh_sources(db, current_app.config)
        except SourceError:
            pass
    return ok(build_market(db, root(), source_id, keyword, sort))


@bp.post("/install")
@require_role("admin")
def install():
    data = payload()
    source_id = data.get("source_id")
    plugin_id = data.get("plugin_id")
    if not isinstance(source_id, str) or not source_id or not valid_plugin_id(plugin_id):
        return fail(400, "source_id 或 plugin_id 参数非法")
    try:
        result = install_plugin(get_db(), root(), source_id, plugin_id, current_app.config, audit)
    except SourceError as exc:
        return source_failure(exc)
    return ok(result, "安装成功")


@bp.post("/uninstall")
@require_role("admin")
def uninstall():
    plugin_id = payload().get("id")
    try:
        remove_plugin(get_db(), root(), plugin_id)
    except SourceError as exc:
        return source_failure(exc)
    return ok({"id": plugin_id}, "卸载成功")


@bp.post("/installed")
def installed():
    db = get_db()
    items = []
    for path in sorted(root().iterdir(), key=lambda item: item.name) if root().exists() else []:
        if path.is_dir() and not path.is_symlink() and valid_plugin_id(path.name):
            items.append(installed_item(db, path))
    return ok({"items": items})


@bp.post("/info")
def info():
    plugin_id = payload().get("id")
    path = plugin_path(plugin_id)
    if not path or not path.is_dir() or path.is_symlink():
        return fail(404, "插件不存在")
    manifest = read_manifest(path)
    if manifest is None:
        return fail(422, "插件 manifest.json 无效")
    db = get_db()
    good, errors = audit(path)
    status = state(db, plugin_id)
    sensitive = manifest.get("sensitive_permissions") or []
    return ok({
        "manifest": manifest,
        "enabled": status["enabled"],
        "audit_ok": good,
        "errors": errors,
        "authorized": not sensitive or status["authorized"],
        **cached_metadata(db, plugin_id, status["source_id"]),
    })


@bp.post("/toggle")
@require_role("admin")
def toggle():
    data = payload()
    plugin_id = data.get("id")
    enabled = data.get("enabled")
    path = plugin_path(plugin_id)
    if not isinstance(enabled, bool):
        return fail(400, "enabled 必须是布尔值")
    if not path or not path.is_dir() or path.is_symlink():
        return fail(404, "插件不存在")
    good, errors = audit(path)
    if enabled and not good:
        return fail(422, "插件语法审核未通过,不允许加载", {"id": plugin_id, "audit_ok": False, "errors": errors})
    db = get_db()
    db.execute(
        """INSERT INTO plugin_state(id,enabled) VALUES(?,?)
           ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,updated_at=CURRENT_TIMESTAMP""",
        (plugin_id, int(enabled)),
    )
    db.commit()
    return ok({"id": plugin_id, "enabled": enabled, "audit_ok": good})


@bp.post("/check_update")
def check_update():
    db = get_db()
    updates = []
    for path in sorted(root().iterdir(), key=lambda item: item.name) if root().exists() else []:
        if not path.is_dir() or path.is_symlink() or not valid_plugin_id(path.name):
            continue
        current = semver_installed_version(root(), path.name)
        status = state(db, path.name)
        entry = find_cached_item(db, path.name, status["source_id"])
        if entry and is_newer(entry["item"].get("version"), current):
            updates.append({"id": path.name, "current": current, "latest": entry["item"]["version"]})
    return ok({"updates": updates})


@bp.post("/authorize")
@require_role("admin")
def authorize():
    data = payload()
    plugin_id = data.get("id")
    allowed = data.get("allow_sensitive")
    path = plugin_path(plugin_id)
    if not isinstance(allowed, bool):
        return fail(400, "allow_sensitive 必须是布尔值")
    if not path or not path.is_dir() or path.is_symlink():
        return fail(404, "插件不存在")
    db = get_db()
    db.execute(
        """INSERT INTO plugin_state(id,sensitive_authorized) VALUES(?,?)
           ON CONFLICT(id) DO UPDATE SET sensitive_authorized=excluded.sensitive_authorized,
           updated_at=CURRENT_TIMESTAMP""",
        (plugin_id, int(allowed)),
    )
    db.commit()
    return ok({"id": plugin_id, "authorized": allowed})


@bp.post("/invoke")
def invoke():
    data = payload()
    plugin_id = data.get("id")
    action = data.get("action")
    args = data.get("args", {})
    path = plugin_path(plugin_id)
    if not path or not path.is_dir() or path.is_symlink():
        return fail(404, "插件不存在")
    status = state(get_db(), plugin_id)
    if not status["enabled"]:
        return fail(422, "插件未启用")
    good, errors = audit(path)
    if not good:
        return fail(422, "插件语法审核未通过", {"errors": errors})
    if not isinstance(action, str) or not action or not isinstance(args, dict):
        return fail(400, "action 或 args 参数非法")
    locks = current_app.extensions.setdefault("plugin_locks", {})
    lock = locks.setdefault(plugin_id, threading.Lock())
    with lock:
        result = invoke_plugin(
            path,
            action,
            args,
            status["authorized"],
            current_app.config.get("PLUGIN_TIMEOUT", 30),
            current_app.config.get("PLUGIN_MEMORY_MB", 256),
            current_app.config["DB_PATH"],
            current_app.config["DATA_DIR"],
        )
    if not result["ok"]:
        return fail(503, "插件运行异常", {"error": result["error"]})
    return ok({"result": result["result"], "ui": result.get("ui", {})})


@bp.post("/rating")
def rating():
    plugin_id = payload().get("id")
    if not valid_plugin_id(plugin_id):
        return fail(400, "id 参数非法")
    db = get_db()
    status = state(db, plugin_id)
    entry = find_cached_item(db, plugin_id, status["source_id"])
    if not entry:
        return fail(404, "插件评级不存在")
    item = entry["item"]
    official = entry["source_type"] == "official"
    rating_value = item.get("rating")
    distribution = item.get("distribution")
    if distribution is None and isinstance(rating_value, dict):
        distribution = rating_value.get("distribution")
    return ok({
        "id": plugin_id,
        "rating": rating_value,
        "distribution": distribution,
        "source_type": entry["source_type"],
        "verified": bool(item.get("verified", False)) if official else False,
        "badges": item.get("badges") or [],
    })


@bp.post("/author_rating")
def author_rating():
    author_id = payload().get("author_id")
    if not isinstance(author_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", author_id):
        return fail(400, "author_id 参数非法")
    matches = [entry for entry in cached_items(get_db(), enabled_only=False) if entry["item"].get("author_id") == author_id]
    if not matches:
        return fail(404, "开发者评级不存在")
    official = [entry for entry in matches if entry["source_type"] == "official"]
    selected = official or matches
    selected.sort(key=lambda entry: (entry["source_id"], entry["item"]["id"]))
    first = selected[0]["item"]
    plugins = []
    for entry in selected:
        item = entry["item"]
        plugin_rating = item.get("rating") or {}
        plugins.append({
            "id": item["id"],
            "name": item.get("name", item["id"]),
            "level": plugin_rating.get("level"),
            "score": plugin_rating.get("score"),
        })
    return ok({
        "author_id": author_id,
        "author": first.get("author"),
        "rating": first.get("author_rating"),
        "plugins": plugins,
        "verified": bool(any(entry["item"].get("verified") for entry in selected)) if official else False,
    })
