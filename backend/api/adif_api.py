import io
import uuid

from flask import Blueprint, request, send_file

from backend.core.database import get_db
from backend.core.response import fail, ok
from backend.services.adif_exporter import ADIFExporter


bp = Blueprint("adif", __name__, url_prefix="/api/adif")
exports = {}


@bp.post("/export")
def export_adif():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    rows = get_db().execute("SELECT * FROM log ORDER BY id").fetchall()
    try:
        result = ADIFExporter().export(
            rows,
            date_from=data.get("date_from"),
            date_to=data.get("date_to"),
            band=data.get("band"),
            mode=data.get("mode"),
            station_callsign=data.get("station_callsign"),
        )
    except ValueError as exc:
        return fail(400, str(exc))
    token = "exp_" + uuid.uuid4().hex
    exports[token] = result.content
    return ok({
        "token": token,
        "total": result.total,
        "exported": result.exported,
        "skipped": result.skipped,
        "errors": result.errors,
    })


@bp.post("/download")
def download():
    token = (request.get_json(silent=True) or {}).get("token")
    content = exports.pop(token, None)
    if content is None:
        return fail(404, "导出文件不存在或已过期")
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name="hamlog.adi",
        mimetype="application/octet-stream",
    )
