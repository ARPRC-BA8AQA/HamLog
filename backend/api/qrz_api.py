from flask import Blueprint, request
from backend.core.response import ok, fail

bp = Blueprint("qrz", __name__, url_prefix="/api/qrz")

@bp.post("/lookup")
def lookup():
    callsign = str((request.get_json(silent=True) or {}).get("callsign", "")).strip().upper()
    if not callsign: return fail(400, "callsign 不能为空")
    try:
        from qrz_scraper import QRZScraper
        result = QRZScraper(delay=(0, 0)).lookup(callsign)
        result.update({"url": f"https://www.qrz.com/db/{callsign}", "found": True})
        return ok(result)
    except Exception as exc:
        return fail(503, f"QRZ 查询失败: {exc}")
