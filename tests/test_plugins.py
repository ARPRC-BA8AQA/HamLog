import hashlib
import io
import json
import zipfile

from backend.app import create_app
from backend.plugins import sources


def make_client(tmp_path, official_index):
    config = {
        "auth": {
            "enabled": False,
            "jwt_secret": "test-secret",
            "access_token_expires": 7200,
            "refresh_token_expires": 604800,
        },
        "security": {"cors_origins": ["*"], "csrf_enabled": True, "aes_enabled": False},
        "logging": {"level": "INFO"},
        "plugins": {"enabled": True, "allow_sensitive": False, "sources": ["official"]},
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
        "PLUGIN_OFFICIAL_INDEX": official_index,
    })
    client = app.test_client()
    csrf = client.post("/api/auth/csrf").get_json()["data"]["csrf_token"]
    client.environ_base["HTTP_X_CSRF_TOKEN"] = csrf
    return client


def plugin_manifest(plugin_id, version):
    return {
        "id": plugin_id,
        "name": "Safe Plugin",
        "version": version,
        "author": "Tester",
        "description": "test plugin",
        "entry": "main.py",
        "min_app_version": "2.0.0",
        "api_version": "1",
        "permissions": [],
        "sensitive_permissions": [],
    }


def plugin_zip(plugin_id, version, extra_files=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{plugin_id}/manifest.json", json.dumps(plugin_manifest(plugin_id, version)))
        archive.writestr(
            f"{plugin_id}/main.py",
            "class Plugin:\n"
            "    def __init__(self, ctx): self.ctx = ctx\n"
            "    def invoke(self, action, args): return args\n",
        )
        for name, content in extra_files or []:
            archive.writestr(name, content)
    return output.getvalue()


def index_with(items, source_type="official", name="Test Source"):
    return {
        "source_type": source_type,
        "name": name,
        "api_version": "1",
        "updated_at": "2026-08-14T00:00:00Z",
        "plugins": items,
    }


def source_item(plugin_id, version, archive, **extra):
    return {
        "id": plugin_id,
        "name": "Safe Plugin",
        "version": version,
        "author": "Tester",
        "author_id": "tester",
        "description": "test plugin",
        "permissions": [],
        "sensitive_permissions": [],
        "download_url": f"https://plugins.test/{plugin_id}-{version}.zip",
        "sha256": hashlib.sha256(archive).hexdigest(),
        **extra,
    }


class FakeResponse(io.BytesIO):
    def __init__(self, payload, url):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def fake_http(monkeypatch, responses):
    def open_url(request, timeout=None):
        url = request.full_url
        if url not in responses:
            raise AssertionError(f"unexpected URL: {url}")
        return FakeResponse(responses[url], url)

    monkeypatch.setattr(sources, "urlopen", open_url)
    monkeypatch.setattr(sources.socket, "getaddrinfo", lambda *args, **kwargs: [(sources.socket.AF_INET, sources.socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])


def test_source_market_and_rating_semantics(tmp_path, monkeypatch):
    archive = plugin_zip("safe_plugin", "1.0.0")
    rating = {"score": 4.8, "count": 126, "level": "silver", "trend": 0.2}
    author_rating = {"score": 4.9, "level": "gold", "plugin_count": 1}
    official = index_with([
        source_item(
            "safe_plugin",
            "1.0.0",
            archive,
            rating=rating,
            distribution={"5": 100, "4": 26},
            author_rating=author_rating,
            verified=True,
            badges=["staff_pick"],
        )
    ])
    third_party = index_with(
        [source_item("third_plugin", "1.0.0", plugin_zip("third_plugin", "1.0.0"), rating=rating, verified=True)],
        source_type="official",
        name="Pretend Official",
    )
    fake_http(monkeypatch, {"https://third.test/index.json": json.dumps(third_party).encode()})
    client = make_client(tmp_path, official)

    refreshed = client.post("/api/plugin/source/refresh", json={}).get_json()
    assert refreshed["data"]["refreshed"] == ["official"]
    market = client.post("/api/plugin/market", json={}).get_json()["data"]["items"]
    assert market[0]["source_type"] == "official"
    assert market[0]["verified"] is True

    detail = client.post("/api/plugin/rating", json={"id": "safe_plugin"}).get_json()["data"]
    assert detail["rating"]["score"] == 4.8
    assert detail["distribution"]["5"] == 100
    author = client.post("/api/plugin/author_rating", json={"author_id": "tester"}).get_json()["data"]
    assert author["rating"]["level"] == "gold"
    assert author["plugins"][0]["id"] == "safe_plugin"

    added = client.post(
        "/api/plugin/source/add",
        json={"name": "Third Party", "url": "https://third.test/index.json"},
    ).get_json()["data"]
    assert added["source_type"] == "third_party"
    third_market = client.post("/api/plugin/market", json={"source_id": added["id"]}).get_json()["data"]["items"]
    assert third_market[0]["source_type"] == "third_party"
    assert third_market[0]["verified"] is False
    assert third_market[0]["rating"]["score"] == 4.8

    assert client.post("/api/plugin/source/toggle", json={"id": added["id"], "enabled": False}).status_code == 200
    assert client.post("/api/plugin/market", json={"source_id": added["id"]}).get_json()["data"]["items"] == []
    sources_list = client.post("/api/plugin/source/list", json={}).get_json()["data"]["sources"]
    assert next(item for item in sources_list if item["id"] == added["id"])["enabled"] is False
    assert client.post("/api/plugin/source/delete", json={"id": "official"}).status_code == 403
    assert client.post("/api/plugin/source/delete", json={"id": added["id"]}).status_code == 200
    assert all(
        item["id"] != added["id"]
        for item in client.post("/api/plugin/source/list", json={}).get_json()["data"]["sources"]
    )


def test_install_update_state_persistence_and_uninstall(tmp_path, monkeypatch):
    archive_v1 = plugin_zip("safe_plugin", "1.0.0")
    official = index_with([source_item("safe_plugin", "1.0.0", archive_v1)])
    responses = {"https://plugins.test/safe_plugin-1.0.0.zip": archive_v1}
    fake_http(monkeypatch, responses)
    client = make_client(tmp_path, official)
    client.post("/api/plugin/source/refresh", json={})

    installed = client.post(
        "/api/plugin/install", json={"source_id": "official", "plugin_id": "safe_plugin"}
    ).get_json()
    assert installed["code"] == 200
    assert installed["data"]["audit_ok"] is True
    assert (tmp_path / "plugins" / "safe_plugin" / "main.py").is_file()
    item = client.post("/api/plugin/installed", json={}).get_json()["data"]["items"][0]
    assert item["enabled"] is True
    assert item["source_id"] == "official"

    # A fresh app instance must see source cache and installation state from SQLite.
    restarted = make_client(tmp_path, official)
    persisted = restarted.post("/api/plugin/installed", json={}).get_json()["data"]["items"][0]
    assert persisted["enabled"] is True
    assert restarted.post("/api/plugin/source/list", json={}).get_json()["data"]["sources"][0]["cached_at"]

    archive_v2 = plugin_zip("safe_plugin", "1.1.0")
    responses["https://plugins.test/safe_plugin-1.1.0.zip"] = archive_v2
    official["updated_at"] = "2026-08-14T01:00:00Z"
    official["plugins"] = [source_item("safe_plugin", "1.1.0", archive_v2)]
    restarted.post("/api/plugin/source/refresh", json={"source_id": "official"})
    updates = restarted.post("/api/plugin/check_update", json={}).get_json()["data"]["updates"]
    assert updates == [{"id": "safe_plugin", "current": "1.0.0", "latest": "1.1.0"}]

    assert restarted.post(
        "/api/plugin/install", json={"source_id": "official", "plugin_id": "safe_plugin"}
    ).status_code == 200
    assert json.loads((tmp_path / "plugins" / "safe_plugin" / "manifest.json").read_text())["version"] == "1.1.0"
    assert restarted.post("/api/plugin/check_update", json={}).get_json()["data"]["updates"] == []
    assert restarted.post("/api/plugin/uninstall", json={"id": "safe_plugin"}).status_code == 200
    assert not (tmp_path / "plugins" / "safe_plugin").exists()
    assert restarted.post("/api/plugin/installed", json={}).get_json()["data"]["items"] == []


def test_install_rejects_bad_hash_and_zip_traversal(tmp_path, monkeypatch):
    bad_hash_archive = plugin_zip("hash_plugin", "1.0.0")
    traversal_archive = plugin_zip(
        "path_plugin",
        "1.0.0",
        [("path_plugin/../../escaped.txt", "unsafe")],
    )
    bad_hash_item = source_item("hash_plugin", "1.0.0", bad_hash_archive)
    bad_hash_item["sha256"] = "0" * 64
    official = index_with([
        bad_hash_item,
        source_item("path_plugin", "1.0.0", traversal_archive),
    ])
    fake_http(monkeypatch, {
        "https://plugins.test/hash_plugin-1.0.0.zip": bad_hash_archive,
        "https://plugins.test/path_plugin-1.0.0.zip": traversal_archive,
    })
    client = make_client(tmp_path, official)
    client.post("/api/plugin/source/refresh", json={})

    bad_hash = client.post(
        "/api/plugin/install", json={"source_id": "official", "plugin_id": "hash_plugin"}
    ).get_json()
    assert bad_hash["code"] == 422
    assert "SHA-256" in bad_hash["msg"]
    traversal = client.post(
        "/api/plugin/install", json={"source_id": "official", "plugin_id": "path_plugin"}
    ).get_json()
    assert traversal["code"] == 422
    assert "路径" in traversal["msg"]
    assert not (tmp_path / "plugins" / "hash_plugin").exists()
    assert not (tmp_path / "plugins" / "path_plugin").exists()
    assert not (tmp_path / "escaped.txt").exists()
