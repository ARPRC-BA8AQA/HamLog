import json
import logging
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class PluginContext:
    """Restricted context available inside the plugin child process."""

    app_version = "2.0.0"
    api_version = "1"

    LOG_FIELDS = {
        "Callsign", "Freq", "Year", "Month", "Day", "Time", "Mode",
        "Power_self", "Power_side", "Rst_self", "Rst_side", "QTH", "Device",
        "QSL_RX", "QSL_SEND", "Remarks",
    }

    def __init__(self, plugin_id, plugin_dir, permissions, sensitive_permissions, sensitive_authorized, db_path=None, app_data_dir=None):
        self.plugin_id = plugin_id
        self.plugin_dir = Path(plugin_dir).resolve()
        self.data_dir = (self.plugin_dir / "data").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = set(permissions)
        self.sensitive_permissions = set(sensitive_permissions)
        self.sensitive_authorized = sensitive_authorized
        self.db_path = str(db_path) if db_path else None
        self.app_data_dir = Path(app_data_dir).resolve() if app_data_dir else self.plugin_dir.parent
        self.ui = {"menus": [], "panels": [], "widgets": [], "styles": []}
        self._theme_callbacks = []

    def _require(self, permission):
        declared = permission in self.permissions or permission in self.sensitive_permissions
        if not declared:
            raise PermissionError(f"插件未声明权限: {permission}")
        if permission in self.sensitive_permissions and not self.sensitive_authorized:
            raise PermissionError(f"敏感权限未授权: {permission}")

    def _safe_data_path(self, value):
        path = (self.data_dir / value).resolve()
        if path != self.data_dir and self.data_dir not in path.parents:
            raise PermissionError("文件路径超出插件数据目录")
        return path

    def plugin_data_dir(self):
        return str(self.data_dir)

    def _db(self):
        if not self.db_path:
            raise RuntimeError("数据库不可用")
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def log_debug(self, message): logging.getLogger(f"hamlog.plugin.{self.plugin_id}").debug(message)
    def log_info(self, message): logging.getLogger(f"hamlog.plugin.{self.plugin_id}").info(message)
    def log_warning(self, message): logging.getLogger(f"hamlog.plugin.{self.plugin_id}").warning(message)
    def log_error(self, message): logging.getLogger(f"hamlog.plugin.{self.plugin_id}").error(message)

    def read_file(self, path):
        self._require("file.read")
        return self._safe_data_path(path).read_text(encoding="utf-8")

    def write_file(self, path, data):
        self._require("file.write")
        target = self._safe_data_path(path); target.parent.mkdir(parents=True, exist_ok=True); target.write_text(str(data), encoding="utf-8"); return True

    def get_log(self, log_id):
        self._require("log.read")
        with self._db() as db:
            row = db.execute("SELECT * FROM log WHERE id=?", (log_id,)).fetchone()
        return dict(row) if row else None

    def search_logs(self, keyword):
        self._require("log.read")
        value = f"%{str(keyword or '')[:200]}%"
        with self._db() as db:
            rows = db.execute("SELECT * FROM log WHERE Callsign LIKE ? OR QTH LIKE ? OR Device LIKE ? OR Remarks LIKE ? ORDER BY id DESC LIMIT 500", (value, value, value, value)).fetchall()
        return [dict(row) for row in rows]

    def list_logs(self, page=1, size=50):
        self._require("log.read")
        page = max(1, int(page)); size = min(max(1, int(size)), 500)
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) FROM log").fetchone()[0]
            rows = db.execute("SELECT * FROM log ORDER BY id DESC LIMIT ? OFFSET ?", (size, (page - 1) * size)).fetchall()
        return {"total": total, "page": page, "page_size": size, "items": [dict(row) for row in rows]}

    def add_log(self, value):
        self._require("log.write")
        if not isinstance(value, dict) or not str(value.get("Callsign", "")).strip():
            raise ValueError("Callsign 不能为空")
        fields = {key: item for key, item in value.items() if key in self.LOG_FIELDS}
        fields["Callsign"] = str(fields["Callsign"]).strip().upper()
        names = list(fields)
        with self._db() as db:
            cursor = db.execute(f"INSERT INTO log({','.join(names)}) VALUES({','.join('?' for _ in names)})", [fields[name] for name in names])
        return cursor.lastrowid

    def update_log(self, log_id, value):
        self._require("log.write")
        if not isinstance(value, dict): raise ValueError("日志数据必须是对象")
        fields = {key: item for key, item in value.items() if key in self.LOG_FIELDS}
        if not fields: return False
        if "Callsign" in fields: fields["Callsign"] = str(fields["Callsign"]).strip().upper()
        with self._db() as db:
            cursor = db.execute(f"UPDATE log SET {','.join(f'{key}=?' for key in fields)} WHERE id=?", [*fields.values(), log_id])
        return bool(cursor.rowcount)

    def delete_log(self, log_id):
        self._require("log.write")
        with self._db() as db: cursor = db.execute("DELETE FROM log WHERE id=?", (log_id,))
        return bool(cursor.rowcount)

    def log_stats(self):
        self._require("log.read")
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) FROM log").fetchone()[0]
            modes = {row[0] or "unknown": row[1] for row in db.execute("SELECT Mode,COUNT(*) FROM log GROUP BY Mode")}
        return {"total": total, "by_mode": modes}

    def get_setting(self, key):
        self._require("settings.read")
        if str(key).startswith("qrz_"): raise PermissionError("敏感设置不可通过 settings.read 读取")
        with self._db() as db: row = db.execute("SELECT value FROM settings WHERE key=?", (str(key),)).fetchone()
        return row[0] if row else None

    def get_all_settings(self):
        self._require("settings.read")
        with self._db() as db: rows = db.execute("SELECT key,value FROM settings WHERE key NOT LIKE 'qrz_%'").fetchall()
        return {row[0]: row[1] for row in rows}

    def set_setting(self, key, value):
        self._require("settings.write")
        key = str(key)
        if key.startswith("qrz_"): raise PermissionError("敏感设置不可通过 settings.write 修改")
        with self._db() as db: db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        return True

    def get_qsl(self, project_id):
        self._require("qsl.read")
        with self._db() as db: row = db.execute("SELECT id,name,schema_version,updated_at,content FROM qsl_projects WHERE id=?", (project_id,)).fetchone()
        if not row: return None
        value = dict(row); value["content"] = json.loads(value["content"]); return value

    def list_qsl(self):
        self._require("qsl.read")
        with self._db() as db: rows = db.execute("SELECT id,name,schema_version,updated_at FROM qsl_projects ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def encrypt(self, plaintext):
        from backend.core.crypto import Crypto
        return Crypto(self.app_data_dir / "secret.key").encrypt(str(plaintext))

    def decrypt(self, token):
        self._require("aes.decrypt")
        from backend.core.crypto import Crypto
        return Crypto(self.app_data_dir / "secret.key").decrypt(token)

    def http_get(self, url, timeout=10):
        self._require("network")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}: raise ValueError("只允许 HTTP/HTTPS URL")
        with urlopen(Request(url, headers={"User-Agent": "HamLog-Plugin/1"}), timeout=min(float(timeout), 30)) as response:
            return response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")

    def http_post(self, url, body, timeout=10):
        self._require("network")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}: raise ValueError("只允许 HTTP/HTTPS URL")
        payload = json.dumps(body).encode("utf-8")
        with urlopen(Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "HamLog-Plugin/1"}), timeout=min(float(timeout), 30)) as response:
            return response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")

    def register_menu(self, value): self._require("ui.menu"); self.ui["menus"].append(value)
    def register_panel(self, value): self._require("ui.panel"); self.ui["panels"].append(value)
    def register_widget(self, value): self._require("ui.widget"); self.ui["widgets"].append(value)

    def get_theme(self):
        self._require("ui.theme")
        mode = self.get_setting("theme") if "settings.read" in self.permissions else "light"
        return {"mode": mode or "light", "colors": {}}

    def on_theme_change(self, callback):
        self._require("ui.theme")
        if not callable(callback): raise TypeError("主题回调必须可调用")
        self._theme_callbacks.append(callback)

    def inject_style(self, css):
        self._require("ui.style")
        lowered = css.lower()
        if "@import" in lowered or "expression(" in lowered or "javascript:" in lowered:
            raise ValueError("CSS 包含不安全内容")
        scoped_blocks = []
        for block in str(css).split("}"):
            if not block.strip(): continue
            selectors, separator, declarations = block.partition("{")
            if not separator or "@" in selectors: raise ValueError("CSS 规则格式非法")
            scoped_selectors = ", ".join(f"#plugin-{self.plugin_id} {selector.strip()}" for selector in selectors.split(",") if selector.strip())
            scoped_blocks.append(f"{scoped_selectors} {{{declarations}}}")
        scoped = "\n".join(scoped_blocks)
        self.ui["styles"].append(scoped)
