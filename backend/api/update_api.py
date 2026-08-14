import uuid
from pathlib import Path

from flask import Blueprint, current_app, request

from backend.core.response import fail, ok
from backend.core.decorators import require_role
from backend.services.update_service import (
    UpdateService,
    UpdateUnavailable,
    start_download,
)


bp = Blueprint("update", __name__, url_prefix="/api/update")


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _service():
    service = current_app.config.get("UPDATE_SERVICE")
    if service is None:
        service = current_app.extensions.setdefault("update_service", UpdateService())
    return service


@bp.post("/check")
def check():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    current_version = data.get("current_version")
    if not isinstance(current_version, str) or not current_version.strip():
        return fail(400, "current_version 不能为空")
    config = current_app.config["HAMLOG_CONFIG"].get("update", {})
    try:
        result = _service().check(
            current_version,
            check_url=config.get("check_url"),
            timeout=config.get("timeout", 10),
        )
    except ValueError as exc:
        return fail(400, str(exc))
    except UpdateUnavailable as exc:
        return fail(503, str(exc))
    current_app.extensions["last_update_check"] = result
    return ok(result)


@bp.post("/download")
@require_role("admin")
def download():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    exe_url = data.get("exe_url")
    if not isinstance(exe_url, str) or not exe_url:
        return fail(400, "exe_url 不能为空")
    service = _service()
    if not service.available():
        return fail(503, "更新网络依赖不可用")
    try:
        service.validate_download_url(exe_url)
    except ValueError as exc:
        return fail(400, str(exc))
    checked = current_app.extensions.get("last_update_check") or {}
    if exe_url != checked.get("exe_url"):
        return fail(409, "请先检查更新，且只能下载检查结果中的安装包")
    task_id = "upd_" + uuid.uuid4().hex
    destination = Path(current_app.config["DATA_DIR"]) / "updates" / f"{task_id}.exe"
    task = {
        "status": "pending",
        "percent": 0,
        "speed_kbps": 0,
        "error": None,
        "file": str(destination),
        "sha256": checked.get("sha256"),
    }
    try:
        thread = start_download(service, exe_url, destination, task, checked.get("sha256"))
    except ValueError as exc:
        return fail(400, str(exc))
    current_app.extensions.setdefault("update_tasks", {})[task_id] = task
    current_app.extensions.setdefault("update_threads", {})[task_id] = thread
    return ok({"task_id": task_id})


@bp.post("/progress")
def progress():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return fail(400, "task_id 不能为空")
    task = current_app.extensions.setdefault("update_tasks", {}).get(task_id)
    if not task:
        return fail(404, "更新任务不存在")
    return ok({key: task.get(key) for key in ("status", "percent", "speed_kbps", "error")})


@bp.post("/install")
@require_role("admin")
def install():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    task_id = data.get("task_id")
    task = current_app.extensions.setdefault("update_tasks", {}).get(task_id)
    if not task:
        return fail(404, "更新任务不存在")
    if task.get("status") != "done":
        return fail(409, "更新包尚未下载完成")
    try:
        _service().install(task["file"])
    except UpdateUnavailable as exc:
        return fail(503, str(exc))
    task["status"] = "installing"
    return ok({"task_id": task_id, "status": "installing"})
