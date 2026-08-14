import uuid
from pathlib import Path
from flask import Blueprint, current_app, request, send_file
from backend.core.database import get_db
from backend.core.response import ok, fail

bp = Blueprint("adif", __name__, url_prefix="/api/adif")
exports = {}

@bp.post("/export")
def export_adif():
    data = request.get_json(silent=True) or {}; rows = get_db().execute("SELECT * FROM log ORDER BY id").fetchall(); lines = ["<ADIF_VER:5>3.1.0 <EOH>"]
    for row in rows:
        fields = {"CALL": row["Callsign"], "FREQ": row["Freq"], "MODE": row["Mode"], "RST_SENT": row["Rst_self"], "RST_RCVD": row["Rst_side"], "QTH": row["QTH"], "COMMENT": row["Remarks"]}
        lines.append(" ".join(f"<{key}:{len(str(value or ''))}>{value or ''}" for key, value in fields.items()) + " <EOR>")
    token = "exp_" + uuid.uuid4().hex; exports[token] = "\n".join(lines).encode(); return ok({"token": token, "total": len(rows), "exported": len(rows), "skipped": 0, "errors": []})

@bp.post("/download")
def download():
    token = (request.get_json(silent=True) or {}).get("token")
    if token not in exports: return fail(404, "导出文件不存在或已过期")
    path = Path(current_app.config["DATA_DIR"]) / (token + ".adi")
    path.write_bytes(exports.pop(token))
    return send_file(path, as_attachment=True, download_name="hamlog.adi", mimetype="application/octet-stream")
