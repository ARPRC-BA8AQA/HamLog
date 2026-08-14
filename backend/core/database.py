import json
import sqlite3
from pathlib import Path
from flask import current_app, g

DB_SCHEMA_VERSION = 2

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
CREATE TABLE IF NOT EXISTS revoked_tokens (jti TEXT PRIMARY KEY, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS app_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
 level TEXT, source TEXT, message TEXT);
CREATE INDEX IF NOT EXISTS idx_logs_time ON app_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_level ON app_logs(level);
CREATE TABLE IF NOT EXISTS plugin_state (id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
 sensitive_authorized INTEGER NOT NULL DEFAULT 0, source_id TEXT, source_type TEXT,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS plugin_sources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
 source_type TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT, cached_at TEXT, index_json TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS plugin_market_cache (
 source_id TEXT NOT NULL, plugin_id TEXT NOT NULL, item_json TEXT NOT NULL,
 cached_at TEXT NOT NULL, PRIMARY KEY(source_id, plugin_id),
 FOREIGN KEY(source_id) REFERENCES plugin_sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plugin_market_cache_plugin
 ON plugin_market_cache(plugin_id);
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _set_schema_version(db, version):
    db.execute(
        "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(version),),
    )


def migrate(db):
    """Apply idempotent migrations for existing SQLite databases."""
    db.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    current = db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    try:
        version = int(current[0]) if current else 0
    except (TypeError, ValueError):
        version = 0
    columns = {row[1] for row in db.execute("PRAGMA table_info(log)")}
    for name, definition in (
        ("Freq", "TEXT"),
        ("Year", "INTEGER"),
        ("Month", "INTEGER"),
        ("Day", "INTEGER"),
        ("Time", "TEXT"),
        ("Mode", "TEXT"),
        ("Power_self", "TEXT"),
        ("Power_side", "TEXT"),
        ("Rst_self", "TEXT"),
        ("Rst_side", "TEXT"),
        ("QTH", "TEXT"),
        ("Device", "TEXT"),
        ("CreateTime", "TEXT"),
        ("QSL_RX", "TEXT DEFAULT ''"),
        ("QSL_SEND", "TEXT DEFAULT ''"),
        ("Remarks", "TEXT DEFAULT ''"),
    ):
        if name not in columns:
            db.execute(f"ALTER TABLE log ADD COLUMN {name} {definition}")
    if version < 1:
        _set_schema_version(db, 1)
        version = 1
    if version < 2:
        _set_schema_version(db, 2)
    # Index creation is idempotent and also repairs databases whose metadata
    # was copied without all schema objects.
    db.execute("CREATE INDEX IF NOT EXISTS idx_log_date ON log(Year,Month,Day)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_log_mode ON log(Mode)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON app_logs(timestamp)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON app_logs(level)")
    db.execute("DELETE FROM revoked_tokens WHERE expires_at <= strftime('%s','now')")
    db.commit()
    return DB_SCHEMA_VERSION

def init_db(app):
    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(app.config["DB_PATH"]) as db:
        db.executescript(SCHEMA)
        # plugin_state predates source-aware installation. Keep existing databases
        # usable without requiring a separate migration command.
        columns = {row[1] for row in db.execute("PRAGMA table_info(plugin_state)")}
        for name, definition in (("source_id", "TEXT"), ("source_type", "TEXT")):
            if name not in columns:
                db.execute(f"ALTER TABLE plugin_state ADD COLUMN {name} {definition}")
        migrate(db)


def schema_status():
    db = get_db()
    row = db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    try:
        version = int(row[0]) if row else 0
    except (TypeError, ValueError):
        version = 0
    return {"schema_version": str(version), "pending_migrations": max(DB_SCHEMA_VERSION - version, 0)}

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
