import sqlite3
import time
import zipfile
import hashlib
from pathlib import Path

import pytest

from backend.app import create_app
from backend.services.lotw_service import LoTWService, LoTWUnavailable
from backend.services.tqsl_service import TQSLUnavailable
from backend.services.update_service import UpdateService, UpdateUnavailable
from backend.core.time_sync import TimeSyncUnavailable


def make_client(tmp_path, **services):
    config = {
        "auth": {
            "enabled": False,
            "jwt_secret": "test-secret",
            "access_token_expires": 7200,
        },
        "security": {"cors_origins": ["*"], "csrf_enabled": True, "aes_enabled": False},
        "logging": {"level": "INFO", "keep_days": 1},
        "time_sync": {"servers": ["ntp.test"], "timeout": 1, "auto_elevate": True},
        "update": {"timeout": 1},
    }
    app_config = {
        "TESTING": True,
        "HOST": "127.0.0.1",
        "PORT": 5000,
        "DEBUG": False,
        "DATA_DIR": str(tmp_path),
        "DB_PATH": str(tmp_path / "test.db"),
        "HAMLOG_CONFIG": config,
        "PLUGIN_DIR": str(tmp_path / "plugins"),
    }
    app_config.update(services)
    app = create_app(app_config)
    client = app.test_client()
    csrf = client.post("/api/auth/csrf").get_json()["data"]["csrf_token"]
    client.environ_base["HTTP_X_CSRF_TOKEN"] = csrf
    return app, client


def wait_for_task(client, path, task_id):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        data = client.post(path, json={"task_id": task_id}).get_json()["data"]
        if data["status"] in {"done", "error", "installing"}:
            return data
        time.sleep(0.01)
    pytest.fail(f"task {task_id} did not finish")


class FakeTQSL:
    def __init__(self):
        self.sign_args = None

    def find_tqsl(self, search_drives=None):
        return {"tqsl_path": "C:\\Program Files\\TrustedQSL\\tqsl.exe", "version": "2.7.1"}

    def list_certificates(self, tqsl_path=None):
        return {"certs": [{"callsign": "BA8AQA", "station": "Mianyang", "expire": "2028-01-01"}]}

    def sign_adif(self, adif_data, tqsl_path, station_location, duplicate_strategy):
        self.sign_args = (tqsl_path, station_location, duplicate_strategy)
        assert b"<EOR>" in adif_data
        return b"signed-tq8"


class FakeLoTW:
    def available(self):
        return True

    def upload(self, tq8_data):
        assert tq8_data == b"signed-tq8"
        return {"uploaded": None, "duplicates": 0, "errors": [], "message": "上传完成"}


class MissingTQSL(FakeTQSL):
    def find_tqsl(self, search_drives=None):
        raise TQSLUnavailable("未找到 TQSL")


def test_lotw_endpoints_and_async_progress(tmp_path):
    tqsl = FakeTQSL()
    _, client = make_client(tmp_path, TQSL_SERVICE=tqsl, LOTW_SERVICE=FakeLoTW())

    found = client.post("/api/lotw/find_tqsl", json={"search_drives": None})
    assert found.status_code == 200
    assert found.get_json()["data"]["version"] == "2.7.1"
    certs = client.post("/api/lotw/list_certs", json={"tqsl_path": None})
    assert certs.get_json()["data"]["certs"][0]["callsign"] == "BA8AQA"

    added = client.post(
        "/api/log/add",
        json={
            "Callsign": "BA8AQA",
            "Freq": "144.000",
            "Mode": "FM",
            "Year": 2026,
            "Month": 8,
            "Day": 8,
            "Time": "0230",
        },
    )
    assert added.status_code == 200
    token = client.post("/api/adif/export", json={}).get_json()["data"]["token"]
    started = client.post(
        "/api/lotw/upload",
        json={
            "tqsl_path": None,
            "station_location": "Mianyang",
            "adif_token": token,
            "duplicate_strategy": "replace",
        },
    )
    assert started.status_code == 200
    progress = wait_for_task(client, "/api/lotw/progress", started.get_json()["data"]["task_id"])
    assert progress["status"] == "done"
    assert progress["uploaded"] == 1
    assert tqsl.sign_args[1:] == ("Mianyang", "replace")


def test_lotw_unavailable_and_validation_return_errors(tmp_path):
    _, client = make_client(tmp_path, TQSL_SERVICE=MissingTQSL(), LOTW_SERVICE=FakeLoTW())
    missing = client.post("/api/lotw/find_tqsl", json={})
    assert missing.status_code == 503
    assert missing.get_json()["code"] == 503
    invalid = client.post("/api/lotw/upload", json={"duplicate_strategy": "invalid"})
    assert invalid.status_code == 400


class FakeUpdate(UpdateService):
    def __init__(self):
        super().__init__(http_get=lambda *args, **kwargs: None)
        self.installed = None

    def check(self, current_version, check_url=None, timeout=10):
        return {
            "has_update": True,
            "latest_version": "Release 2.1.0",
            "force_update": False,
            "changelog": "changes",
            "exe_url": "https://example.test/hamlog.exe",
        }

    def download(self, exe_url, destination, progress):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"installer")
        progress(100, 5)
        return destination

    def install(self, package_path):
        self.installed = Path(package_path)


class MissingUpdate(FakeUpdate):
    def available(self):
        return False

    def check(self, current_version, check_url=None, timeout=10):
        raise UpdateUnavailable("更新服务器不可达")


def test_update_check_download_progress_and_install(tmp_path):
    service = FakeUpdate()
    _, client = make_client(tmp_path, UPDATE_SERVICE=service)
    checked = client.post("/api/update/check", json={"current_version": "Release 2.0.0"})
    assert checked.status_code == 200
    assert checked.get_json()["data"]["has_update"] is True
    assert client.post("/api/update/download", json={"exe_url": "file:///tmp/a.exe"}).status_code == 400

    started = client.post("/api/update/download", json={"exe_url": "https://example.test/hamlog.exe"})
    task_id = started.get_json()["data"]["task_id"]
    progress = wait_for_task(client, "/api/update/progress", task_id)
    assert progress == {"status": "done", "percent": 100, "speed_kbps": 0, "error": None}
    installed = client.post("/api/update/install", json={"task_id": task_id})
    assert installed.get_json()["data"]["status"] == "installing"
    assert service.installed.read_bytes() == b"installer"


def test_update_unavailable_returns_503(tmp_path):
    _, client = make_client(tmp_path, UPDATE_SERVICE=MissingUpdate())
    checked = client.post("/api/update/check", json={"current_version": "Release 2.0.0"})
    assert checked.status_code == 503
    downloaded = client.post("/api/update/download", json={"exe_url": "https://example.test/a.exe"})
    assert downloaded.status_code == 503


def test_update_download_verifies_sha256(tmp_path):
    payload = b"trusted-installer"

    class Response:
        status_code = 200
        headers = {"content-length": str(len(payload))}
        def iter_content(self, chunk_size): yield payload
        def close(self): return None

    service = UpdateService(http_get=lambda *args, **kwargs: Response())
    destination = tmp_path / "update.exe"
    service.download("https://example.test/update.exe", destination, lambda *_: None, hashlib.sha256(payload).hexdigest())
    assert destination.read_bytes() == payload
    with pytest.raises(UpdateUnavailable, match="SHA-256"):
        service.download("https://example.test/update.exe", destination, lambda *_: None, "0" * 64)
    assert not destination.exists()


class FakeTimeSync:
    def sync(self, servers, timeout, auto_elevate):
        assert servers == ["ntp.test"]
        return {"offset_ms": -120, "synced": True, "server": servers[0], "elevated": True}


class MissingTimeSync:
    def sync(self, servers, timeout, auto_elevate):
        raise TimeSyncUnavailable("NTP 不可达")


def test_time_sync_and_status(tmp_path):
    _, client = make_client(tmp_path, TIME_SYNC_SERVICE=FakeTimeSync())
    synced = client.post("/api/system/sync_time", json={"servers": ["ntp.test"]})
    assert synced.status_code == 200
    assert synced.get_json()["data"]["offset_ms"] == -120
    status = client.post("/api/system/sync_status", json={}).get_json()["data"]
    assert status["last_sync"] is not None
    assert status["offset_ms"] == -120


def test_time_sync_unavailable_returns_503(tmp_path):
    _, client = make_client(tmp_path, TIME_SYNC_SERVICE=MissingTimeSync())
    response = client.post("/api/system/sync_time", json={"servers": ["ntp.test"]})
    assert response.status_code == 503
    assert response.get_json()["code"] == 503


def test_system_log_query_and_stats(tmp_path):
    app, client = make_client(tmp_path)
    with sqlite3.connect(app.config["DB_PATH"]) as db:
        db.executemany(
            "INSERT INTO app_logs(timestamp,level,source,message) VALUES(?,?,?,?)",
            [
                ("2026-08-08T02:00:00", "INFO", "qrz", "查询 BA8AQA"),
                ("2026-08-08T02:01:00", "ERROR", "lotw", "上传失败"),
                ("2026-08-08T02:02:00", "INFO", "qrz", "查询 BD8AAA"),
            ],
        )
    queried = client.post(
        "/api/system/log/query",
        json={"level": "info", "keyword": "BA8", "source": "qrz", "limit": 10, "offset": 0},
    )
    assert queried.status_code == 200
    assert queried.get_json()["data"]["total"] == 1
    assert queried.get_json()["data"]["items"][0]["source"] == "qrz"
    stats = client.post("/api/system/log/stats", json={}).get_json()["data"]
    assert stats["total"] == 3
    assert stats["by_level"]["INFO"] == 2
    assert stats["by_level"]["CRITICAL"] == 0


def test_backup_creates_restorable_zip_and_applies_retention(tmp_path):
    app, client = make_client(tmp_path)
    (tmp_path / "qsl").mkdir()
    (tmp_path / "qsl" / "card.hamqsl").write_text("{}", encoding="utf-8")
    client.post("/api/log/add", json={"Callsign": "BA8AQA"})

    first = client.post("/api/system/backup", json={"keep_count": 1})
    assert first.status_code == 200
    time.sleep(0.01)
    second = client.post("/api/system/backup", json={"keep_count": 1})
    data = second.get_json()["data"]
    backups = list((tmp_path / "backups").glob("backup_*.zip"))
    assert len(backups) == 1
    assert backups[0].name == data["file"]
    assert data["size"] == backups[0].stat().st_size
    with zipfile.ZipFile(backups[0]) as archive:
        assert set(archive.namelist()) == {"Log.db", "qsl/card.hamqsl"}
        restored = tmp_path / "restored.db"
        restored.write_bytes(archive.read("Log.db"))
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT Callsign FROM log").fetchone()[0] == "BA8AQA"


def test_new_api_routes_are_post_only(tmp_path):
    _, client = make_client(tmp_path)
    for path in (
        "/api/lotw/find_tqsl",
        "/api/update/check",
        "/api/system/sync_time",
        "/api/system/log/query",
        "/api/system/backup",
    ):
        response = client.get(path)
        assert response.status_code == 405
        assert response.get_json()["code"] == 405


def test_lotw_response_parser_requires_documented_acceptance_marker():
    class Response:
        status_code = 200
        text = "<!-- .UPL. accepted --><!-- .UPLMESSAGE. 1 QSO accepted -->"

    service = LoTWService(http_post=lambda *args, **kwargs: Response())
    assert service.upload(b"signed")["errors"] == []

    class InvalidResponse:
        status_code = 200
        text = "login page"

    service = LoTWService(http_post=lambda *args, **kwargs: InvalidResponse())
    with pytest.raises(LoTWUnavailable):
        service.upload(b"signed")
