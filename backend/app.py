from pathlib import Path
from flask import Flask, request
from flask_cors import CORS
from backend.config import ROOT, load_config
from backend.core.database import close_db, init_db
from backend.core.logger import configure_logging
from backend.core.response import fail
from backend.core.security import validate_csrf
from backend.core.decorators import authenticate_request

def create_app(test_config=None):
    app = Flask(__name__, static_folder="../front", static_url_path="")
    if test_config and "server" not in test_config:
        config = load_config()
        app.config.update(test_config)
        app.config.setdefault("DATA_DIR", str(ROOT / "data"))
        app.config.setdefault("DB_PATH", str(ROOT / "data" / "Log.db"))
        app.config.setdefault("HAMLOG_CONFIG", config)
    else:
        config = test_config or load_config()
        app.config.update({"HOST": config["server"]["host"], "PORT": config["server"]["port"], "DEBUG": config["server"].get("debug", False), "DATA_DIR": str(ROOT / "data"), "DB_PATH": str(ROOT / "data" / "Log.db"), "HAMLOG_CONFIG": config})
    app.config.setdefault("JSON_AS_ASCII", False)
    app.secret_key = config["auth"].get("jwt_secret", "")
    configure_logging(ROOT, config["logging"].get("level", "INFO")); init_db(app); app.teardown_appcontext(close_db)
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
    app.config.setdefault("PLUGIN_DIR", str(ROOT / "plugins"))
    for blueprint in (log_bp, settings_bp, qsl_bp, system_bp, auth_bp, adif_bp, qrz_bp, plugin_bp, intertime_bp): app.register_blueprint(blueprint)
    @app.before_request
    def csrf_guard():
        if not request.path.startswith("/api/"):
            return None
        if request.endpoint and request.endpoint.startswith("auth."):
            return None
        authentication_error = authenticate_request()
        if authentication_error:
            return authentication_error
        if request.method == "POST":
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
