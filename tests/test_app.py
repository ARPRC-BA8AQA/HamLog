import json
import io
import os
from pathlib import Path

import pytest
from unittest.mock import patch

from backend.app import create_app

def make_client(tmp_path, auth_enabled=False):
    config = {
        "auth": {"enabled": auth_enabled, "jwt_secret": "test-secret", "access_token_expires": 7200, "refresh_token_expires": 604800},
        "security": {"cors_origins": ["*"], "csrf_enabled": True, "aes_enabled": False},
        "logging": {"level": "INFO"},
    }
    app = create_app({
        "TESTING": True,
        "HOST": "127.0.0.1",
        "PORT": 5000,
        "DEBUG": False,
        "DATA_DIR": str(tmp_path),
        "DB_PATH": str(tmp_path / "test.db"),
        "HAMLOG_CONFIG": config,
        "PLUGIN_DIR": str(tmp_path / "plugins"),
        "PLUGIN_TIMEOUT": 2,
    })
    client = app.test_client()
    csrf = client.post("/api/auth/csrf").get_json()["data"]["csrf_token"]
    client.environ_base["HTTP_X_CSRF_TOKEN"] = csrf
    return client

@pytest.fixture()
def client(tmp_path):
    return make_client(tmp_path)

def test_log_crud_and_search(client):
    response = client.post("/api/log/add", json={"Callsign": "ba8aqa", "Freq": "144MHz", "Mode": "FM", "QTH": "Mianyang"})
    assert response.status_code == 200
    log_id = response.get_json()["data"]["id"]
    response = client.post("/api/log/list", json={"keyword": "BA8"})
    assert response.get_json()["data"]["total"] == 1
    response = client.post("/api/log/update", json={"id": log_id, "log": {"Remarks": "test"}})
    assert response.get_json()["code"] == 200
    response = client.post("/api/log/delete", json={"id": log_id})
    assert response.get_json()["code"] == 200

def test_qsl_round_trip(client):
    content = {"schema_version": "0.9", "canvas": {"width": 148, "height": 105}, "elements": [], "unknown": True}
    response = client.post("/api/qsl/save", json={"name": "test", "content": content})
    assert response.status_code == 200
    project_id = response.get_json()["data"]["id"]
    loaded = client.post("/api/qsl/load", json={"id": project_id}).get_json()["data"]
    assert loaded["content"]["schema_version"] == "1.0"
    assert loaded["content"]["format"] == "hamlog-qsl"
    app = client.application
    project_file = Path(app.config["DATA_DIR"]) / "qsl" / "projects" / f"{project_id}.hamqsl"
    assert json.loads(project_file.read_text(encoding="utf-8"))["format"] == "hamlog-qsl"
    assert client.post("/api/qsl/delete", json={"id": project_id}).status_code == 200
    assert not project_file.exists()

def test_qsl_private_export_and_import(client):
    content = {"schema_version": "1.0", "format": "hamlog-qsl", "canvas": {"width": 148, "height": 105}, "elements": [], "assets": {}}
    project_id = client.post("/api/qsl/save", json={"name": "card", "content": content}).get_json()["data"]["id"]
    token = client.post("/api/qsl/export_private", json={"id": project_id}).get_json()["data"]["token"]
    exported = client.post("/api/qsl/download", json={"token": token})
    assert exported.status_code == 200
    imported = client.post("/api/qsl/import_private", data={"file": (io.BytesIO(exported.data), "card.hamqsl")}, content_type="multipart/form-data")
    assert imported.get_json()["code"] == 200

def test_qsl_public_png_and_pdf_export(client):
    content = {
        "schema_version": "1.0", "format": "hamlog-qsl",
        "canvas": {"width": 40, "height": 30, "unit": "mm", "dpi": 72},
        "background": {"type": "color", "color": "#ffffff"},
        "elements": [{"id": "call", "type": "text", "x": 2, "y": 2, "w": 30, "h": 8, "content": "{log.callsign}", "style": {"font_size": 12}}],
        "assets": {},
    }
    project_id = client.post("/api/qsl/save", json={"name": "public", "content": content}).get_json()["data"]["id"]
    for export_format, prefix, mimetype in (("png", b"\x89PNG", "image/png"), ("pdf", b"%PDF", "application/pdf")):
        exported = client.post("/api/qsl/export_public", json={"id": project_id, "format": export_format, "data": {"log.callsign": "BA8AQA"}, "dpi": 72})
        assert exported.status_code == 200
        downloaded = client.post("/api/qsl/download", json={"token": exported.get_json()["data"]["token"]})
        assert downloaded.status_code == 200
        assert downloaded.mimetype == mimetype
        assert downloaded.data.startswith(prefix)

def test_qsl_rejects_external_or_invalid_assets(client):
    base = {"schema_version": "1.0", "canvas": {"width": 148, "height": 105}, "elements": [], "assets": {}}
    external = {**base, "assets": {"asset": {"type": "image", "dataurl": "https://example.test/a.png"}}}
    assert client.post("/api/qsl/save", json={"content": external}).status_code == 400
    oversized = {**base, "canvas": {"width": 5001, "height": 105}}
    assert client.post("/api/qsl/save", json={"content": oversized}).status_code == 400

def test_authentication_and_user_management(tmp_path):
    client = make_client(tmp_path, auth_enabled=True)
    assert client.post("/api/auth/status", json={}).get_json()["data"]["setup_required"] is True
    assert client.post("/api/log/list", json={}).status_code == 401
    created = client.post("/api/auth/user/create", json={"username": "admin", "password": "password123", "role": "user"})
    assert created.get_json()["data"]["role"] == "admin"
    logged_in = client.post("/api/auth/login", json={"username": "admin", "password": "password123"}).get_json()["data"]
    assert client.post("/api/auth/status", json={}).get_json()["data"]["setup_required"] is False
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + logged_in["access_token"]
    assert client.post("/api/log/list", json={}).status_code == 200
    assert client.post("/api/auth/user/list", json={}).get_json()["data"]["items"][0]["username"] == "admin"

def test_logout_revocation_survives_new_app_instance(tmp_path):
    client = make_client(tmp_path, auth_enabled=True)
    client.post("/api/auth/user/create", json={"username": "admin", "password": "password123"})
    token = client.post("/api/auth/login", json={"username": "admin", "password": "password123"}).get_json()["data"]["access_token"]
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
    assert client.post("/api/auth/logout", json={}).status_code == 200
    restarted = make_client(tmp_path, auth_enabled=True)
    restarted.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
    assert restarted.post("/api/log/list", json={}).status_code == 401

def test_regular_user_cannot_run_admin_operations(tmp_path):
    client = make_client(tmp_path, auth_enabled=True)
    client.post("/api/auth/user/create", json={"username": "admin", "password": "password123"})
    admin = client.post("/api/auth/login", json={"username": "admin", "password": "password123"}).get_json()["data"]
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + admin["access_token"]
    client.post("/api/auth/user/create", json={"username": "operator", "password": "password123", "role": "user"})
    user = client.post("/api/auth/login", json={"username": "operator", "password": "password123"}).get_json()["data"]
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + user["access_token"]
    for path, payload in (
        ("/api/log/clear", {"confirm": "CLEAR"}),
        ("/api/plugin/source/refresh", {"source_id": None}),
        ("/api/system/aes_disable", {}),
        ("/api/system/backup", {"keep_count": 1}),
    ):
        assert client.post(path, json=payload).status_code == 403

def test_csrf_is_required_for_mutation(tmp_path):
    client = make_client(tmp_path)
    client.environ_base.pop("HTTP_X_CSRF_TOKEN")
    assert client.post("/api/log/add", json={"Callsign": "BA8AQA"}).status_code == 403

def test_aes_uses_environment_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HAMLOG_AES_KEY", "00" * 32)
    from backend.core.crypto import Crypto
    crypto = Crypto(tmp_path / "must-not-exist.key")
    token = crypto.encrypt("secret")
    assert crypto.decrypt(token) == "secret"
    assert not (tmp_path / "must-not-exist.key").exists()

def test_plugin_sandbox_invoke(client, tmp_path):
    plugin = tmp_path / "plugins" / "echo_plugin"; plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(json.dumps({"id": "echo_plugin", "name": "Echo", "version": "1.0.0", "author": "test", "entry": "main.py", "min_app_version": "2.0.0", "api_version": "1", "permissions": [], "sensitive_permissions": []}), encoding="utf-8")
    (plugin / "main.py").write_text("class Plugin:\n    def __init__(self, ctx): self.ctx = ctx\n    def invoke(self, action, args): return {'action': action, 'value': args.get('value')}\n", encoding="utf-8")
    assert client.post("/api/plugin/toggle", json={"id": "echo_plugin", "enabled": True}).status_code == 200
    invoked = client.post("/api/plugin/invoke", json={"id": "echo_plugin", "action": "echo", "args": {"value": 73}})
    assert invoked.get_json()["data"]["result"]["value"] == 73

def test_plugin_rejects_undeclared_network_import(client, tmp_path):
    plugin = tmp_path / "plugins" / "net_plugin"; plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(json.dumps({"id": "net_plugin", "name": "Network", "version": "1.0.0", "author": "test", "entry": "main.py", "min_app_version": "2.0.0", "api_version": "1", "permissions": [], "sensitive_permissions": []}), encoding="utf-8")
    (plugin / "main.py").write_text("import socket\nclass Plugin:\n    def __init__(self, ctx): self.ctx = ctx\n    def invoke(self, action, args): return socket.gethostname()\n", encoding="utf-8")
    assert client.post("/api/plugin/toggle", json={"id": "net_plugin", "enabled": True}).status_code == 200
    response = client.post("/api/plugin/invoke", json={"id": "net_plugin", "action": "host", "args": {}})
    assert response.status_code == 503
    assert "ctx.http_get" in response.get_json()["data"]["error"]

def test_plugin_context_log_read_and_write_permissions(client, tmp_path):
    client.post("/api/log/add", json={"Callsign": "BA8AQA"})
    plugin = tmp_path / "plugins" / "log_plugin"; plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(json.dumps({"id": "log_plugin", "name": "Logs", "version": "1.0.0", "author": "test", "entry": "main.py", "min_app_version": "2.0.0", "api_version": "1", "permissions": ["log.read", "log.write"], "sensitive_permissions": []}), encoding="utf-8")
    (plugin / "main.py").write_text("class Plugin:\n    def __init__(self, ctx): self.ctx=ctx\n    def invoke(self, action, args):\n        before=self.ctx.list_logs()\n        new_id=self.ctx.add_log({'Callsign':'w1aw'})\n        return {'before':before['total'],'new':self.ctx.get_log(new_id)['Callsign']}\n", encoding="utf-8")
    client.post("/api/plugin/toggle", json={"id": "log_plugin", "enabled": True})
    result = client.post("/api/plugin/invoke", json={"id": "log_plugin", "action": "run", "args": {}})
    assert result.status_code == 200
    assert result.get_json()["data"]["result"] == {"before": 1, "new": "W1AW"}

def test_intertime_config_persists_and_uses_tcp(client):
    saved = client.post("/api/intertime/set", json={"nodes": ["example.test:8443"], "timeout": 1, "interval": 10, "enabled": True, "display_names": {"example.test:8443": "Example"}})
    assert saved.status_code == 200
    assert client.post("/api/intertime/get", json={}).get_json()["data"]["nodes"] == ["example.test:8443"]
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    with patch("backend.api.intertime_api.socket.create_connection", return_value=Connection()) as connect:
        tested = client.post("/api/intertime/test", json={})
    assert tested.get_json()["data"]["results"][0]["ok"] is True
    connect.assert_called_once_with(("example.test", 8443), timeout=1.0)
