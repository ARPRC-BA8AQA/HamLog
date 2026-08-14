import json
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, send_file
from io import BytesIO
from backend.core.database import get_db
from backend.core.response import ok, fail
from backend.services.qsl_design_service import normalize, import_content, content_json

exports = {}

bp = Blueprint("qsl", __name__, url_prefix="/api/qsl")

def save_project(autosave=False):
    data = request.get_json(silent=True) or {}; project_id = data.get("id") or "proj_" + uuid.uuid4().hex[:12]; name = data.get("name") or "未命名卡片"
    try: content = normalize(data.get("content"))
    except ValueError as exc: return fail(400, str(exc))
    now = datetime.now(timezone.utc).isoformat()
    db = get_db(); db.execute("INSERT INTO qsl_projects(id,name,schema_version,updated_at,content) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,schema_version=excluded.schema_version,updated_at=excluded.updated_at,content=excluded.content", (project_id, name, content["schema_version"], now, content_json(content))); db.commit()
    return ok({"id": project_id, "updated_at": now, **({"saved": True} if autosave else {})}, "ok" if autosave else "保存成功")

@bp.post("/save")
def save(): return save_project()

@bp.post("/autosave")
def autosave(): return save_project(True)

@bp.post("/list")
def list_projects():
    rows = get_db().execute("SELECT id,name,updated_at FROM qsl_projects ORDER BY updated_at DESC").fetchall()
    return ok({"items": [dict(row) for row in rows]})

@bp.post("/load")
def load():
    project_id = (request.get_json(silent=True) or {}).get("id"); row = get_db().execute("SELECT * FROM qsl_projects WHERE id=?", (project_id,)).fetchone()
    if not row: return fail(404, "QSL 项目不存在")
    return ok({"id": row["id"], "name": row["name"], "content": json.loads(row["content"]), "updated_at": row["updated_at"]})

@bp.post("/delete")
def delete():
    project_id = (request.get_json(silent=True) or {}).get("id"); db = get_db(); cur = db.execute("DELETE FROM qsl_projects WHERE id=?", (project_id,)); db.commit()
    return ok(None, "删除成功") if cur.rowcount else fail(404, "QSL 项目不存在")

@bp.post("/export_private")
def export_private():
    project_id = (request.get_json(silent=True) or {}).get("id")
    row = get_db().execute("SELECT * FROM qsl_projects WHERE id=?", (project_id,)).fetchone()
    if not row: return fail(404, "QSL 项目不存在")
    payload = row["content"].encode("utf-8"); token = "qsl_exp_" + uuid.uuid4().hex; exports[token] = {"name": row["name"], "mime": "application/x-hamlog-qsl+json", "data": payload}
    return ok({"token": token, "filename": f"{row['name']}.hamqsl"})

@bp.post("/download")
def download():
    token = (request.get_json(silent=True) or {}).get("token"); item = exports.pop(token, None)
    if not item: return fail(404, "导出文件不存在或已过期")
    return send_file(BytesIO(item["data"]), as_attachment=True, download_name=f"{item['name']}.hamqsl", mimetype=item["mime"])

@bp.post("/import_private")
def import_private():
    uploaded = request.files.get("file")
    if not uploaded: return fail(400, "缺少 file 文件")
    try: content = import_content(uploaded.read())
    except ValueError as exc: return fail(422, str(exc))
    project_id = "proj_" + uuid.uuid4().hex[:12]; name = uploaded.filename.rsplit("/", 1)[-1].removesuffix(".hamqsl") or "导入卡片"; now = datetime.now(timezone.utc).isoformat(); db = get_db()
    db.execute("INSERT INTO qsl_projects(id,name,schema_version,updated_at,content) VALUES(?,?,?,?,?)", (project_id, name, content["schema_version"], now, content_json(content))); db.commit()
    return ok({"id": project_id, "name": name, "migrated": True, "schema_version": content["schema_version"]}, "导入成功")

@bp.post("/upload_asset")
def upload_asset():
    uploaded = request.files.get("file")
    if not uploaded: return fail(400, "缺少 file 文件")
    data = uploaded.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024: return fail(400, "素材超过 10MB 限制")
    import base64
    mime = uploaded.mimetype if uploaded.mimetype in {"image/png", "image/jpeg", "image/webp", "image/gif"} else None
    if not mime: return fail(422, "只支持 PNG/JPEG/WebP/GIF 素材")
    asset_id = "asset_" + uuid.uuid4().hex[:12]
    return ok({"asset_id": asset_id, "dataurl": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"})

@bp.post("/data_fields")
def data_fields():
    fields = [("log.callsign", "对方呼号"), ("log.date", "通联日期"), ("log.freq", "频率"), ("log.mode", "模式"), ("log.rst", "信号报告"), ("station.my_callsign", "我的呼号"), ("station.my_qth", "我的 QTH")]
    return ok({"fields": [{"key": key, "label": label, "group": "通联" if key.startswith("log.") else "本台"} for key, label in fields]})
