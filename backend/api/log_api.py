from datetime import date
from flask import Blueprint, request, current_app
from backend.core.database import get_db, row_dict
from backend.core.response import ok, fail

bp = Blueprint("log", __name__, url_prefix="/api/log")
FIELDS = ["Callsign", "Freq", "Year", "Month", "Day", "Time", "Mode", "Power_self", "Power_side", "Rst_self", "Rst_side", "QTH", "Device", "QSL_RX", "QSL_SEND", "Remarks"]

def body():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}

def validate_log(data):
    call = str(data.get("Callsign", "")).strip().upper()
    if not call:
        return None, "Callsign 不能为空"
    if len(call) > 20:
        return None, "Callsign 长度非法"
    normalized = {key: data.get(key) for key in FIELDS if key in data}
    normalized["Callsign"] = call
    for key in ("Year", "Month", "Day"):
        if key in normalized and normalized[key] is not None:
            try: normalized[key] = int(normalized[key])
            except (ValueError, TypeError): return None, f"{key} 必须是数字"
    return normalized, None

@bp.post("/list")
def list_logs():
    data = body(); page = max(int(data.get("page", 1) or 1), 1); size = min(max(int(data.get("page_size", 50) or 50), 1), 500)
    clauses, params = [], []
    keyword = data.get("keyword")
    if keyword:
        clauses.append("(Callsign LIKE ? OR QTH LIKE ? OR Device LIKE ? OR Remarks LIKE ?)")
        params += [f"%{keyword}%"] * 4
    for field in ("Callsign", "Mode"):
        if data.get(field.lower()) is not None: clauses.append(f"{field} = ?"); params.append(data[field.lower()])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    db = get_db(); total = db.execute("SELECT COUNT(*) FROM log" + where, params).fetchone()[0]
    order = "ASC" if str(data.get("order", "desc")).lower() == "asc" else "DESC"
    rows = db.execute(f"SELECT * FROM log{where} ORDER BY id {order} LIMIT ? OFFSET ?", params + [size, (page - 1) * size]).fetchall()
    return ok({"total": total, "page": page, "page_size": size, "items": [row_dict(r) for r in rows]})

@bp.post("/get")
def get_log():
    item = get_db().execute("SELECT * FROM log WHERE id = ?", (body().get("id"),)).fetchone()
    return ok(row_dict(item)) if item else fail(404, "日志不存在")

@bp.post("/add")
def add_log():
    item, error = validate_log(body())
    if error: return fail(422, error)
    keys = list(item); db = get_db(); cur = db.execute(f"INSERT INTO log ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [item[k] for k in keys]); db.commit()
    return ok({"id": cur.lastrowid}, "日志添加成功")

@bp.post("/update")
def update_log():
    data = body(); log_id = data.get("id")
    patch = data.get("log") if isinstance(data.get("log"), dict) else {}
    patch = {k: v for k, v in patch.items() if k in FIELDS}
    if not patch: return fail(400, "没有可更新字段")
    if "Callsign" in patch: patch["Callsign"] = str(patch["Callsign"]).strip().upper()
    for key in ("Year", "Month", "Day"):
        if key in patch and patch[key] is not None:
            try: patch[key] = int(patch[key])
            except (ValueError, TypeError): return fail(400, f"{key} 必须是数字")
    db = get_db(); cur = db.execute(f"UPDATE log SET {','.join(f'{k} = ?' for k in patch)} WHERE id = ?", list(patch.values()) + [log_id]); db.commit()
    return ok({"id": log_id}, "更新成功") if cur.rowcount else fail(404, "日志不存在")

@bp.post("/delete")
def delete_log():
    db = get_db(); cur = db.execute("DELETE FROM log WHERE id = ?", (body().get("id"),)); db.commit()
    return ok(None, "删除成功") if cur.rowcount else fail(404, "日志不存在")

@bp.post("/search")
def search_logs():
    data = body(); keyword = str(data.get("keyword", "")); limit = min(int(data.get("limit", 100) or 100), 500)
    rows = get_db().execute("SELECT * FROM log WHERE Callsign LIKE ? OR QTH LIKE ? OR Device LIKE ? OR Remarks LIKE ? ORDER BY id DESC LIMIT ?", [f"%{keyword}%"] * 4 + [limit]).fetchall()
    return ok({"items": [row_dict(r) for r in rows]})

@bp.post("/stats")
def stats():
    db = get_db(); total = db.execute("SELECT COUNT(*) FROM log").fetchone()[0]; today = date.today();
    today_count = db.execute("SELECT COUNT(*) FROM log WHERE Year=? AND Month=? AND Day=?", (today.year, today.month, today.day)).fetchone()[0]
    return ok({"total": total, "today": today_count, "this_month": db.execute("SELECT COUNT(*) FROM log WHERE Year=? AND Month=?", (today.year, today.month)).fetchone()[0], "by_band": {}, "by_mode": {}})

@bp.post("/clear")
def clear_logs():
    if body().get("confirm") != "CLEAR": return fail(400, "需要输入 CLEAR 确认")
    db = get_db(); db.execute("DELETE FROM log"); db.commit(); return ok(None, "日志已清空")
