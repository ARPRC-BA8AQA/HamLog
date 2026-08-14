import os
import sys
from pathlib import Path
import secrets
from copy import deepcopy
import yaml

SOURCE_ROOT = Path(__file__).resolve().parent.parent


def _resource_root():
    bundle_root = getattr(sys, "_MEIPASS", None)
    return Path(bundle_root) if bundle_root else SOURCE_ROOT


def _runtime_root():
    override = os.environ.get("HAMLOG_HOME")
    if override:
        return Path(override).expanduser()
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "HamLog"
    return SOURCE_ROOT


RESOURCE_ROOT = _resource_root()
ROOT = _runtime_root()
DEFAULT_CONFIG = {
    "server": {"host": "127.0.0.1", "port": 5000, "debug": False},
    "auth": {"enabled": False, "jwt_secret": "", "access_token_expires": 7200, "refresh_token_expires": 604800},
    "security": {"cors_origins": ["http://127.0.0.1:5000"], "csrf_enabled": True, "aes_enabled": False},
    "logging": {"level": "INFO", "keep_days": 30},
    "qso": {"input_timezone": "UTC"},
    "plugins": {"enabled": True, "allow_sensitive": False, "sources": ["official"]},
    "qsl": {"autosave_interval": 10},
    "time_sync": {"enabled": True, "servers": ["ntp.ntsc.ac.cn", "pool.ntp.org"], "timeout": 2, "auto_elevate": True},
    "update": {"timeout": 10},
}

def load_config(path=None):
    path = Path(path or ROOT / "config.yaml")
    config = deepcopy(DEFAULT_CONFIG)
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        for section, values in loaded.items():
            if isinstance(values, dict) and isinstance(config.get(section), dict):
                config[section] = {**config[section], **values}
    generated_secret = not path.exists()
    if not config["auth"].get("jwt_secret"):
        config["auth"]["jwt_secret"] = secrets.token_urlsafe(32)
        generated_secret = True
    if generated_secret:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return config


def save_config(config, path=None):
    target = Path(path or ROOT / "config.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.replace(target)
    try:
        target.chmod(0o600)
    except OSError:
        pass
