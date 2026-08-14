import json
from pathlib import Path

import pytest

from backend.app import create_app

@pytest.fixture()
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "HOST": "127.0.0.1",
        "PORT": 5000,
        "DEBUG": False,
        "DATA_DIR": str(tmp_path),
        "DB_PATH": str(tmp_path / "test.db"),
        "HAMLOG_CONFIG": {"logging": {"level": "INFO"}, "security": {"cors_origins": ["*"]}},
    })
    client = app.test_client()
    csrf = client.post("/api/auth/csrf").get_json()["data"]["csrf_token"]
    client.environ_base["HTTP_X_CSRF_TOKEN"] = csrf
    return client

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
