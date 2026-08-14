import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


class BackupError(RuntimeError):
    """Raised when the application data cannot be backed up."""


def _snapshot_database(db_path, target):
    source = sqlite3.connect(str(db_path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def create_backup(data_dir, db_path, keep_count=10, config_path=None, plugin_dir=None):
    if not isinstance(keep_count, int) or isinstance(keep_count, bool) or not 1 <= keep_count <= 100:
        raise ValueError("keep_count 必须是 1 到 100 的整数")
    data_dir = Path(data_dir)
    db_path = Path(db_path)
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = "backup_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + ".zip"
    target = backup_dir / filename
    if target.exists():
        filename = "backup_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") + ".zip"
        target = backup_dir / filename

    try:
        with tempfile.TemporaryDirectory(prefix="hamlog-backup-") as temporary:
            snapshot = Path(temporary) / "Log.db"
            _snapshot_database(db_path, snapshot)
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, "Log.db")
                if config_path and Path(config_path).is_file():
                    archive.write(config_path, "config.yaml")
                if data_dir.exists():
                    for path in data_dir.rglob("*"):
                        if not path.is_file() or backup_dir in path.parents:
                            continue
                        if path.resolve() == db_path.resolve():
                            continue
                        archive.write(path, path.relative_to(data_dir).as_posix())
                if plugin_dir and Path(plugin_dir).is_dir():
                    for path in Path(plugin_dir).rglob("*"):
                        if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts:
                            archive.write(path, "plugins/" + path.relative_to(plugin_dir).as_posix())
    except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        target.unlink(missing_ok=True)
        raise BackupError(f"备份失败: {exc}") from exc

    backups = sorted(backup_dir.glob("backup_*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_backup in backups[keep_count:]:
        old_backup.unlink(missing_ok=True)
    return {"file": filename, "size": target.stat().st_size}
