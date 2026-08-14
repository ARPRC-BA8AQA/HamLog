from collections import Counter
from datetime import datetime, timezone

from flask import Blueprint, current_app, request

from backend.core.database import get_db, row_dict
from backend.core.response import fail, ok
from backend.core.decorators import require_role
from backend.services.qso_service import QSO_FIELDS, filter_rows, normalize_qso
from backend.services.radio import frequency_to_band


bp = Blueprint("log", __name__, url_prefix="/api/log")
FIELDS = list(QSO_FIELDS)


def body():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _input_timezone():
    return current_app.config["HAMLOG_CONFIG"].get("qso", {}).get("input_timezone", "UTC")


def _pagination(data):
    try:
        page = max(int(data.get("page", 1) or 1), 1)
        size = min(max(int(data.get("page_size", 50) or 50), 1), 500)
    except (TypeError, ValueError) as exc:
        raise ValueError("page 和 page_size 必须是整数") from exc
    return page, size


@bp.post("/list")
def list_logs():
    data = body()
    try:
        page, size = _pagination(data)
    except ValueError as exc:
        return fail(400, str(exc))
    clauses, params = [], []
    keyword = data.get("keyword")
    if keyword:
        clauses.append("(Callsign LIKE ? OR QTH LIKE ? OR Device LIKE ? OR Remarks LIKE ?)")
        params += [f"%{keyword}%"] * 4
    if data.get("callsign") not in (None, ""):
        clauses.append("Callsign = ? COLLATE NOCASE")
        params.append(str(data["callsign"]).strip())
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    order = "ASC" if str(data.get("order", "desc")).lower() == "asc" else "DESC"
    rows = [dict(row) for row in get_db().execute(f"SELECT * FROM log{where} ORDER BY id {order}", params).fetchall()]
    try:
        rows = filter_rows(rows, data.get("date_from"), data.get("date_to"), data.get("band"), data.get("mode"))
    except ValueError as exc:
        return fail(400, str(exc))
    start = (page - 1) * size
    return ok({"total": len(rows), "page": page, "page_size": size, "items": rows[start:start + size]})


@bp.post("/get")
def get_log():
    item = get_db().execute("SELECT * FROM log WHERE id = ?", (body().get("id"),)).fetchone()
    return ok(row_dict(item)) if item else fail(404, "日志不存在")


@bp.post("/add")
def add_log():
    try:
        item = normalize_qso(body(), _input_timezone())
    except ValueError as exc:
        return fail(422, str(exc))
    keys = list(item)
    db = get_db()
    cur = db.execute(
        f"INSERT INTO log ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
        [item[key] for key in keys],
    )
    db.commit()
    return ok({"id": cur.lastrowid}, "日志添加成功")


@bp.post("/update")
def update_log():
    data = body()
    log_id = data.get("id")
    requested = data.get("log") if isinstance(data.get("log"), dict) else {}
    patch = {key: value for key, value in requested.items() if key in FIELDS}
    if not patch:
        return fail(400, "没有可更新字段")
    db = get_db()
    existing = db.execute("SELECT * FROM log WHERE id = ?", (log_id,)).fetchone()
    if not existing:
        return fail(404, "日志不存在")
    merged = dict(existing)
    merged.update(patch)
    for extra in ("timezone", "utc_offset"):
        if extra in requested:
            merged[extra] = requested[extra]
    try:
        changes_datetime = any(key in patch for key in ("Year", "Month", "Day", "Time"))
        normalized = normalize_qso(
            merged,
            _input_timezone() if changes_datetime else "UTC",
            require_datetime_pair=changes_datetime,
        )
    except ValueError as exc:
        return fail(422, str(exc))
    update_keys = set(patch)
    if any(key in patch for key in ("Year", "Month", "Day", "Time")):
        update_keys.update(("Year", "Month", "Day", "Time"))
    values = {key: normalized.get(key) for key in FIELDS if key in update_keys}
    cursor = db.execute(
        f"UPDATE log SET {','.join(f'{key} = ?' for key in values)} WHERE id = ?",
        list(values.values()) + [log_id],
    )
    db.commit()
    return ok({"id": log_id}, "更新成功") if cursor.rowcount else fail(404, "日志不存在")


@bp.post("/delete")
def delete_log():
    db = get_db()
    cursor = db.execute("DELETE FROM log WHERE id = ?", (body().get("id"),))
    db.commit()
    return ok(None, "删除成功") if cursor.rowcount else fail(404, "日志不存在")


@bp.post("/search")
def search_logs():
    data = body()
    keyword = str(data.get("keyword", ""))
    try:
        limit = min(max(int(data.get("limit", 100) or 100), 1), 500)
    except (TypeError, ValueError):
        return fail(400, "limit 必须是整数")
    rows = get_db().execute(
        "SELECT * FROM log WHERE Callsign LIKE ? OR QTH LIKE ? OR Device LIKE ? OR Remarks LIKE ? ORDER BY id DESC LIMIT ?",
        [f"%{keyword}%"] * 4 + [limit],
    ).fetchall()
    return ok({"items": [row_dict(row) for row in rows]})


@bp.post("/stats")
def stats():
    rows = [dict(row) for row in get_db().execute("SELECT * FROM log").fetchall()]
    today = datetime.now(timezone.utc).date()
    dated = [(row, (row.get("Year"), row.get("Month"), row.get("Day"))) for row in rows]
    by_band = Counter(filter(None, (frequency_to_band(row.get("Freq")) for row in rows)))
    by_mode = Counter(str(row.get("Mode")).strip().upper() for row in rows if row.get("Mode"))
    return ok({
        "total": len(rows),
        "today": sum(parts == (today.year, today.month, today.day) for _, parts in dated),
        "this_month": sum(parts[:2] == (today.year, today.month) for _, parts in dated),
        "by_band": dict(sorted(by_band.items())),
        "by_mode": dict(sorted(by_mode.items())),
    })


@bp.post("/clear")
@require_role("admin")
def clear_logs():
    if body().get("confirm") != "CLEAR":
        return fail(400, "需要输入 CLEAR 确认")
    db = get_db()
    db.execute("DELETE FROM log")
    db.commit()
    return ok(None, "日志已清空")
