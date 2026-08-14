import logging
import sqlite3
import sys
from logging.handlers import TimedRotatingFileHandler

import pytest

from backend.app import create_app
from backend.services.qrz_client import QRZClient


def make_app(tmp_path, monkeypatch=None, aes_key=False):
    if aes_key and monkeypatch:
        monkeypatch.setenv("HAMLOG_AES_KEY", "01" * 32)
    config = {
        "auth": {"enabled": False, "jwt_secret": "test-secret"},
        "security": {"cors_origins": ["*"], "csrf_enabled": True},
        "logging": {"level": "DEBUG", "keep_days": 7},
        "qso": {"input_timezone": "UTC"},
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
    })
    client = app.test_client()
    token = client.post("/api/auth/csrf").get_json()["data"]["csrf_token"]
    client.environ_base["HTTP_X_CSRF_TOKEN"] = token
    return app, client


@pytest.fixture()
def app_client(tmp_path):
    return make_app(tmp_path)


def test_qso_validation_utc_filters_and_stats(app_client):
    _, client = app_client
    invalid = client.post("/api/log/add", json={
        "Callsign": "W1AW", "Year": 2026, "Month": 2, "Day": 30, "Time": "1200",
    })
    assert invalid.status_code == 422
    assert client.post("/api/log/add", json={
        "Callsign": "W1AW", "Year": 2026, "Month": 8, "Day": 14,
    }).status_code == 422

    first = client.post("/api/log/add", json={
        "Callsign": "w1aw",
        "Freq": "14.074MHz",
        "Year": 2026,
        "Month": 8,
        "Day": 14,
        "Time": "0030",
        "Mode": "ft8",
        "timezone": "+08:00",
    })
    assert first.status_code == 200
    first_id = first.get_json()["data"]["id"]
    stored = client.post("/api/log/get", json={"id": first_id}).get_json()["data"]
    assert (stored["Year"], stored["Month"], stored["Day"], stored["Time"]) == (2026, 8, 13, "1630")

    client.post("/api/log/add", json={
        "Callsign": "K1ABC", "Freq": "144MHz", "Year": 2026,
        "Month": 8, "Day": 14, "Time": "120000", "Mode": "FM",
    })
    filtered = client.post("/api/log/list", json={
        "band": "20m", "mode": "ft8", "date_from": "2026-08-13", "date_to": "2026-08-13",
    }).get_json()["data"]
    assert filtered["total"] == 1
    assert filtered["items"][0]["Callsign"] == "W1AW"
    assert client.post("/api/log/list", json={"date_from": "2026-08-15", "date_to": "2026-08-14"}).status_code == 400

    stats = client.post("/api/log/stats", json={}).get_json()["data"]
    assert stats["by_band"] == {"20m": 1, "2m": 1}
    assert stats["by_mode"] == {"FM": 1, "FT8": 1}


def test_adif_export_fields_filtering_and_skips(app_client):
    _, client = app_client
    client.post("/api/log/add", json={
        "Callsign": "W1AW", "Freq": "14074kHz", "Year": 2026, "Month": 8,
        "Day": 14, "Time": "1234", "Mode": "USB", "Rst_self": "59",
        "Power_self": "5W", "QSL_RX": "2026-08-15", "Remarks": "Field day",
    })
    client.post("/api/log/add", json={"Callsign": "K1ABC", "Freq": "14.2MHz", "Mode": "SSB"})
    response = client.post("/api/adif/export", json={"band": "20m", "station_callsign": "N0CALL"})
    data = response.get_json()["data"]
    assert (data["total"], data["exported"], data["skipped"]) == (2, 1, 1)
    assert data["errors"][0]["error"].endswith("QSO_DATE, TIME_ON")

    downloaded = client.post("/api/adif/download", json={"token": data["token"]})
    text = downloaded.data.decode("utf-8")
    for field in (
        "<ADIF_VER:5>3.1.0",
        "<CALL:4>W1AW",
        "<QSO_DATE:8:D>20260814",
        "<TIME_ON:4:T>1234",
        "<BAND:3>20m",
        "<FREQ:6:N>14.074",
        "<MODE:3>SSB",
        "<SUBMODE:3>USB",
        "<TX_PWR:1:N>5",
        "<QSLRDATE:8:D>20260815",
        "<STATION_CALLSIGN:6>N0CALL",
    ):
        assert field in text
    assert text.endswith("<EOR>\r\n")
    assert client.post("/api/adif/download", json={"token": data["token"]}).status_code == 404

    client.post("/api/log/add", json={
        "Callsign": "N1FT8", "Freq": "14.074MHz", "Year": 2026,
        "Month": 8, "Day": 14, "Time": "1300", "Mode": "FT8",
    })
    ft8 = client.post("/api/adif/export", json={"mode": "FT8"}).get_json()["data"]
    ft8_text = client.post("/api/adif/download", json={"token": ft8["token"]}).data.decode()
    assert "<MODE:4>MFSK" in ft8_text
    assert "<SUBMODE:3>FT8" in ft8_text


def test_qrz_credentials_are_encrypted_used_and_cleared(tmp_path, monkeypatch):
    app, client = make_app(tmp_path, monkeypatch, aes_key=True)
    configured = client.post("/api/qrz/set_credential", json={
        "username": "operator", "password": "very-secret", "encrypt": True,
    })
    assert configured.status_code == 200
    with sqlite3.connect(app.config["DB_PATH"]) as db:
        values = dict(db.execute("SELECT key,value FROM settings WHERE key LIKE 'qrz_%'"))
    assert values["qrz_username_encrypted"] != "operator"
    assert values["qrz_password_encrypted"] != "very-secret"
    visible_settings = client.post("/api/settings/get_all", json={}).get_json()["data"]
    assert not any(key.startswith("qrz_") for key in visible_settings)

    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def lookup(self, callsign, login=False):
            return {"callsign": callsign, "found": True, "logged_in": login}

    app.config["QRZ_CLIENT_FACTORY"] = FakeClient
    result = client.post("/api/qrz/lookup", json={"callsign": "w1aw", "login": True})
    assert result.get_json()["data"]["logged_in"] is True
    assert (seen["username"], seen["password"]) == ("operator", "very-secret")

    cleared = client.post("/api/qrz/clear_credential", json={})
    assert cleared.get_json()["data"]["removed"] is True
    assert client.post("/api/qrz/lookup", json={"callsign": "W1AW", "login": True}).status_code == 400


def test_qrz_parser_handles_standard_fields_and_biography():
    import base64

    biography = base64.b64encode(b"<p>ARRL station</p>").decode()
    html = f"""
    <div id="calldata">W1AW USA QSL: Direct Email: test@example.com Grid: FN31pr Class: Club LoTW eQSL</div>
    <script>Base64.decode("{biography}")</script>
    """
    result = QRZClient.parse(html, "W1AW")
    assert result["country"] == "USA"
    assert result["email"] == "test@example.com"
    assert result["grid"] == "FN31pr"
    assert result["bio"] == "ARRL station"
    assert result["lotw"] is True and result["eqsl"] is True


def test_unified_logging_is_daily_persisted_and_queryable(app_client):
    _, client = app_client
    logger = logging.getLogger("hamlog.business")
    logger.error("radio failure")
    handlers = logging.getLogger("hamlog").handlers
    daily = next(handler for handler in handlers if isinstance(handler, TimedRotatingFileHandler))
    assert daily.when == "MIDNIGHT"
    assert daily.utc is True
    assert sys.excepthook.__module__ == "backend.core.logger"

    queried = client.post("/api/system/log/query", json={
        "level": "ERROR", "source": "business", "keyword": "radio failure",
    }).get_json()["data"]
    assert queried["total"] == 1
    stats = client.post("/api/system/log/stats", json={}).get_json()["data"]
    assert stats["by_level"]["ERROR"] >= 1


def test_legacy_database_is_migrated_and_versioned(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE log(id INTEGER PRIMARY KEY, Callsign TEXT NOT NULL)")
        db.execute("INSERT INTO log(Callsign) VALUES('W1AW')")
    app, client = make_app(tmp_path)
    assert app.config["DB_PATH"] == str(tmp_path / "test.db")

    # Initialize directly against the sparse legacy path to exercise ALTER migrations.
    migration_app = create_app({
        "TESTING": True,
        "HOST": "127.0.0.1",
        "PORT": 5000,
        "DEBUG": False,
        "DATA_DIR": str(tmp_path),
        "DB_PATH": str(db_path),
        "HAMLOG_CONFIG": app.config["HAMLOG_CONFIG"],
        "PLUGIN_DIR": str(tmp_path / "plugins-legacy"),
    })
    migration_client = migration_app.test_client()
    status = migration_client.post("/api/system/db_status", json={}).get_json()["data"]
    assert status == {"schema_version": "2", "pending_migrations": 0}
    with sqlite3.connect(db_path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(log)")}
        indexes = {row[1] for row in db.execute("PRAGMA index_list(log)")}
        assert db.execute("SELECT Callsign FROM log").fetchone()[0] == "W1AW"
    assert {"Freq", "Year", "Time", "Mode", "QSL_RX", "Remarks"}.issubset(columns)
    assert {"idx_log_date", "idx_log_mode"}.issubset(indexes)
