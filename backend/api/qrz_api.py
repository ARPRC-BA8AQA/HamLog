from flask import Blueprint, current_app, request

from backend.core.database import get_db
from backend.core.logger import get_logger
from backend.core.response import fail, ok
from backend.services.qrz_client import QRZAuthenticationError, QRZClient, QRZError, QRZNotFoundError
from backend.services.qrz_credentials import QRZCredentialStore


bp = Blueprint("qrz", __name__, url_prefix="/api/qrz")
log = get_logger("qrz")


def _store():
    return QRZCredentialStore(current_app._get_current_object(), get_db())


@bp.post("/lookup")
def lookup():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    callsign = str(data.get("callsign", "")).strip().upper()
    if not callsign:
        return fail(400, "callsign 不能为空")
    if len(callsign) > 20:
        return fail(400, "callsign 长度非法")
    use_login = data.get("login", False)
    if not isinstance(use_login, bool):
        return fail(400, "login 必须是布尔值")
    credentials = None
    if use_login:
        try:
            credentials = _store().get()
        except ValueError as exc:
            return fail(503, f"QRZ 凭据无法解密: {exc}")
        if not credentials:
            return fail(400, "尚未配置 QRZ 凭据")
    factory = current_app.config.get("QRZ_CLIENT_FACTORY", QRZClient)
    client = factory(
        username=credentials[0] if credentials else None,
        password=credentials[1] if credentials else None,
        delay=(0, 0) if current_app.config.get("TESTING") else (3.0, 6.0),
    )
    try:
        result = client.lookup(callsign, login=use_login)
    except ValueError as exc:
        return fail(400, str(exc))
    except QRZNotFoundError as exc:
        return fail(404, str(exc))
    except (QRZAuthenticationError, QRZError) as exc:
        log.warning("QRZ lookup failed for %s: %s", callsign, exc)
        return fail(503, str(exc))
    log.info("QRZ lookup completed for %s", callsign)
    return ok(result)


@bp.post("/set_credential")
def set_credential():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail(400, "请求体必须是 JSON 对象")
    if data.get("encrypt", True) is not True:
        return fail(400, "QRZ 凭据必须加密存储")
    try:
        _store().set(data.get("username"), data.get("password"))
    except ValueError as exc:
        message = str(exc)
        status = 503 if "HAMLOG_AES_KEY" in message else 400
        return fail(status, message)
    log.info("QRZ credentials configured")
    return ok({"configured": True, "encrypted": True}, "QRZ 凭据已配置")


@bp.post("/clear_credential")
def clear_credential():
    removed = _store().clear()
    log.info("QRZ credentials cleared")
    return ok({"configured": False, "removed": bool(removed)}, "QRZ 凭据已清除")
