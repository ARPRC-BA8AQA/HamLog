import hmac
import secrets
from flask import current_app, request
from backend.core.response import fail

SAFE_ENDPOINTS = {
    "auth.csrf", "auth.login", "auth.refresh", "auth.status",
    "log.list", "log.get", "log.search", "log.stats",
    "settings.get_all", "settings.get", "qsl.list", "qsl.load", "qsl.data_fields",
    "system.info", "system.db_status", "system.sync_status", "plugin.installed", "plugin.info",
    "intertime.get", "intertime.test",
    "system.log_query", "system.log_stats", "lotw.find_tqsl", "lotw.list_certs", "lotw.progress",
    "update.check", "update.progress",
}


def issue_csrf():
    return secrets.token_urlsafe(32)


def validate_csrf():
    config = current_app.config["HAMLOG_CONFIG"].get("security", {})
    if not config.get("csrf_enabled", True) or request.endpoint in SAFE_ENDPOINTS:
        return None
    # Bearer tokens are not automatically sent by browsers and are therefore
    # already protected from cookie-based CSRF attacks.
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return None
    cookie_token = request.cookies.get("hamlog_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        return fail(403, "CSRF Token 缺失或无效")
    return None
