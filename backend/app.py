from pathlib import Path
import time
from flask import Flask, request
from flask_cors import CORS
from backend.config import RESOURCE_ROOT, ROOT, load_config
from backend.core.database import close_db, init_db
from backend.core.logger import configure_logging
from backend.core.response import fail
from backend.core.security import validate_csrf
from backend.core.decorators import authenticate_request

def create_app(test_config=None):
    app = Flask(__name__, static_folder=str(RESOURCE_ROOT / "front"), static_url_path="")
    config = test_config.get("HAMLOG_CONFIG") if test_config and isinstance(test_config.get("HAMLOG_CONFIG"), dict) else load_config()
    server = config.get("server", {})
    app.config.update({"HOST": server.get("host", "127.0.0.1"), "PORT": server.get("port", 5000), "DEBUG": server.get("debug", False), "DATA_DIR": str(ROOT / "data"), "DB_PATH": str(ROOT / "data" / "Log.db"), "HAMLOG_CONFIG": config, "CONFIG_PATH": str(ROOT / "config.yaml")})
    if test_config:
        app.config.update(test_config)
        if app.config.get("TESTING") and "CONFIG_PATH" not in test_config:
            app.config["CONFIG_PATH"] = None
    app.config.setdefault("JSON_AS_ASCII", False)
    app.config.setdefault("RESOURCE_DIR", str(RESOURCE_ROOT))
    app.secret_key = config["auth"].get("jwt_secret", "")
    init_db(app)
    logger = configure_logging(
        Path(app.config["DATA_DIR"]).parent,
        config["logging"].get("level", "INFO"),
        app.config["DB_PATH"],
        config["logging"].get("keep_days", 30),
    )
    app.logger.handlers = list(logger.handlers)
    app.logger.setLevel(logger.level)
    app.logger.propagate = False
    app.teardown_appcontext(close_db)
    app.extensions["started_at"] = time.monotonic()
    CORS(app, resources={r"/api/*": {"origins": config["security"].get("cors_origins", "*")}})
    from backend.api.log_api import bp as log_bp
    from backend.api.settings_api import bp as settings_bp
    from backend.api.qsl_api import bp as qsl_bp
    from backend.api.system_api import bp as system_bp
    from backend.api.auth_api import bp as auth_bp
    from backend.api.adif_api import bp as adif_bp
    from backend.api.qrz_api import bp as qrz_bp
    from backend.api.plugin_api import bp as plugin_bp
    from backend.api.intertime_api import bp as intertime_bp
    from backend.api.lotw_api import bp as lotw_bp
    from backend.api.update_api import bp as update_bp
    app.config.setdefault("PLUGIN_DIR", str(ROOT / "plugins"))
    Path(app.config["PLUGIN_DIR"]).mkdir(parents=True, exist_ok=True)
    for blueprint in (log_bp, settings_bp, qsl_bp, system_bp, auth_bp, adif_bp, qrz_bp, plugin_bp, intertime_bp, lotw_bp, update_bp): app.register_blueprint(blueprint)
    @app.before_request
    def csrf_guard():
        if not request.path.startswith("/api/"):
            return None
        if request.method != "POST":
            return fail(405, "仅支持文档规定的 POST 请求")
        if request.endpoint in {"auth.csrf", "auth.login", "auth.refresh", "auth.status"}:
            return None
        if request.endpoint and request.endpoint.startswith("auth."):
            return validate_csrf()
        authentication_error = authenticate_request()
        if authentication_error:
            return authentication_error
        return validate_csrf()
    @app.errorhandler(404)
    def not_found(_): return fail(404, "资源不存在")
    @app.errorhandler(400)
    def bad_request(_): return fail(400, "请求格式错误")
    @app.errorhandler(405)
    def method_not_allowed(_): return fail(405, "仅支持文档规定的 POST 请求")
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("Unhandled request error", exc_info=error)
        return fail(500, "服务器内部错误")
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def frontend(path):
        from flask import send_from_directory
        return send_from_directory(app.static_folder, path or "index.html")
    return app
