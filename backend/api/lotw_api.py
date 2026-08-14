import uuid
from threading import Thread

from flask import Blueprint, current_app, request

from backend.api.adif_api import exports as adif_exports
from backend.core.response import fail, ok
from backend.services.lotw_service import LoTWService, LoTWUnavailable
from backend.services.tqsl_service import TQSLService, TQSLUnavailable


bp = Blueprint("lotw", __name__, url_prefix="/api/lotw")


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _tqsl_service():
    service = current_app.config.get("TQSL_SERVICE")
    if service is None:
        service = current_app.extensions.setdefault("tqsl_service", TQSLService())
    return service


def _lotw_service():
    service = current_app.config.get("LOTW_SERVICE")
    if service is None:
        service = current_app.extensions.setdefault("lotw_service", LoTWService())
    return service


@bp.post("/find_tqsl")
def find_tqsl():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    search_drives = data.get("search_drives")
    if search_drives is not None and not isinstance(search_drives, list):
        return fail(400, "search_drives 必须是数组或 null")
    try:
        return ok(_tqsl_service().find_tqsl(search_drives))
    except TQSLUnavailable as exc:
        return fail(503, str(exc))


@bp.post("/list_certs")
def list_certs():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    tqsl_path = data.get("tqsl_path")
    if tqsl_path is not None and not isinstance(tqsl_path, str):
        return fail(400, "tqsl_path 必须是字符串或 null")
    try:
        return ok(_tqsl_service().list_certificates(tqsl_path))
    except TQSLUnavailable as exc:
        return fail(503, str(exc))


def _upload_worker(task, tqsl_service, lotw_service, adif_data, tqsl_path, station_location, duplicate_strategy):
    try:
        task.update({"status": "signing", "message": "正在使用 TQSL 签名"})
        tq8_data = tqsl_service.sign_adif(adif_data, tqsl_path, station_location, duplicate_strategy)
        task.update({"status": "uploading", "message": "正在上传到 LoTW"})
        result = lotw_service.upload(tq8_data)
        result["uploaded"] = result.get("uploaded")
        if result["uploaded"] is None:
            result["uploaded"] = adif_data.upper().count(b"<EOR>")
        task.update(result)
        task["status"] = "error" if result.get("errors") else "done"
    except (TQSLUnavailable, LoTWUnavailable, OSError, ValueError) as exc:
        task.update({"status": "error", "errors": [str(exc)], "message": str(exc)})
    except Exception:
        current_app.logger.exception("Unhandled LoTW upload error")
        task.update({"status": "error", "errors": ["LoTW 上传失败"], "message": "LoTW 上传失败"})


@bp.post("/upload")
def upload():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    station_location = data.get("station_location")
    adif_token = data.get("adif_token")
    tqsl_path = data.get("tqsl_path")
    duplicate_strategy = data.get("duplicate_strategy", "skip")
    if not isinstance(station_location, str) or not station_location.strip():
        return fail(400, "station_location 不能为空")
    if not isinstance(adif_token, str) or not adif_token:
        return fail(400, "adif_token 不能为空")
    if tqsl_path is not None and not isinstance(tqsl_path, str):
        return fail(400, "tqsl_path 必须是字符串或 null")
    if duplicate_strategy not in {"skip", "replace", "ask"}:
        return fail(400, "duplicate_strategy 必须是 skip、replace 或 ask")
    adif_data = adif_exports.get(adif_token)
    if adif_data is None:
        return fail(404, "ADIF 导出文件不存在或已过期")

    tqsl_service = _tqsl_service()
    lotw_service = _lotw_service()
    try:
        if tqsl_path:
            tqsl_service._resolve_path(tqsl_path)
        else:
            tqsl_path = tqsl_service.find_tqsl()["tqsl_path"]
    except TQSLUnavailable as exc:
        return fail(503, str(exc))
    if not lotw_service.available():
        return fail(503, "LoTW 网络依赖不可用")

    task_id = "lotw_" + uuid.uuid4().hex
    task = {
        "status": "pending",
        "uploaded": 0,
        "duplicates": 0,
        "errors": [],
        "message": "等待上传",
    }
    current_app.extensions.setdefault("lotw_tasks", {})[task_id] = task
    app = current_app._get_current_object()

    def worker():
        with app.app_context():
            _upload_worker(
                task,
                tqsl_service,
                lotw_service,
                adif_data,
                tqsl_path,
                station_location.strip(),
                duplicate_strategy,
            )

    Thread(target=worker, name=task_id, daemon=True).start()
    return ok({"task_id": task_id})


@bp.post("/progress")
def progress():
    data = _body()
    if data is None:
        return fail(400, "请求体必须是 JSON 对象")
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return fail(400, "task_id 不能为空")
    task = current_app.extensions.setdefault("lotw_tasks", {}).get(task_id)
    return ok(dict(task)) if task else fail(404, "LoTW 上传任务不存在")
