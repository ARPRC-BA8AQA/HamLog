import json
import sqlite3
from pathlib import Path
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, Callsign TEXT NOT NULL, Freq TEXT,
 Year INTEGER, Month INTEGER, Day INTEGER, Time TEXT, Mode TEXT,
 Power_self TEXT, Power_side TEXT, Rst_self TEXT, Rst_side TEXT,
 QTH TEXT, Device TEXT, QSL_RX TEXT DEFAULT '', QSL_SEND TEXT DEFAULT '',
 Remarks TEXT DEFAULT '', CreateTime TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS qsl_projects (id TEXT PRIMARY KEY, name TEXT NOT NULL,
 schema_version TEXT NOT NULL, updated_at TEXT NOT NULL, content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, role TEXT DEFAULT 'admin', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS app_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
 level TEXT, source TEXT, message TEXT);
"""

def init_db(app):
    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(app.config["DB_PATH"]) as db:
        db.executescript(SCHEMA)

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(_=None):
    db = g.pop("db", None)
    if db:
        db.close()

def row_dict(row):
    return dict(row) if row else None

def content_json(content):
    return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
