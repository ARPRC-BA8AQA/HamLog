import json
import logging
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class PluginContext:
    """Restricted context available inside the plugin child process."""

    app_version = "2.0.0"
    api_version = "1"

    def __init__(self, plugin_id, plugin_dir, permissions, sensitive_permissions, sensitive_authorized):
        self.plugin_id = plugin_id
        self.plugin_dir = Path(plugin_dir).resolve()
        self.data_dir = (self.plugin_dir / "data").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = set(permissions)
        self.sensitive_permissions = set(sensitive_permissions)
        self.sensitive_authorized = sensitive_authorized
        self.ui = {"menus": [], "panels": [], "widgets": [], "styles": []}

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

    def inject_style(self, css):
        self._require("ui.style")
        lowered = css.lower()
        if "@import" in lowered or "expression(" in lowered or "javascript:" in lowered:
            raise ValueError("CSS 包含不安全内容")
        self.ui["styles"].append(css)
