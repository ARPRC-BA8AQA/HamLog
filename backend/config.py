from pathlib import Path
import secrets
from copy import deepcopy
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = {
    "server": {"host": "127.0.0.1", "port": 5000, "debug": False},
    "auth": {"enabled": False, "jwt_secret": "", "access_token_expires": 7200},
    "security": {"cors_origins": ["http://127.0.0.1:5000"], "csrf_enabled": True},
    "logging": {"level": "INFO", "keep_days": 30},
    "plugins": {"enabled": True, "allow_sensitive": False, "sources": ["official"]},
    "qsl": {"autosave_interval": 10},
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
    else:
        config["auth"]["jwt_secret"] = secrets.token_urlsafe(32)
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if not config["auth"].get("jwt_secret"):
        config["auth"]["jwt_secret"] = secrets.token_urlsafe(32)
    return config
