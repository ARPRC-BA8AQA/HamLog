import atexit
import faulthandler
import logging
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


_CRASH_FILE = None
_HOOKS_INSTALLED = False


class DatabaseLogHandler(logging.Handler):
    """Persist records without depending on a Flask request context."""

    def __init__(self, db_path):
        super().__init__()
        self.db_path = str(db_path)

    def emit(self, record):
        try:
            import sqlite3
            from flask import current_app, has_app_context

            db_path = current_app.config["DB_PATH"] if has_app_context() else self.db_path
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + "".join(traceback.format_exception(*record.exc_info)).rstrip()
            with sqlite3.connect(db_path, timeout=1) as db:
                db.execute(
                    "INSERT INTO app_logs(timestamp,level,source,message) VALUES(?,?,?,?)",
                    (
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        record.levelname,
                        record.name.removeprefix("hamlog."),
                        message,
                    ),
                )
        except Exception:
            # Logging must not mask an application or database failure.
            pass


def _flush_handlers(logger):
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def _write_uncaught(exc_type, exc_value, exc_tb, label):
    logger = logging.getLogger("hamlog")
    if _CRASH_FILE:
        _CRASH_FILE.write(f"\n{datetime.now(timezone.utc).isoformat()} {label}\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_CRASH_FILE)
        _CRASH_FILE.flush()
    try:
        logger.critical(label, exc_info=(exc_type, exc_value, exc_tb))
        _flush_handlers(logger)
    except Exception:
        pass


def _install_crash_hooks(crash_file):
    global _CRASH_FILE, _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        crash_file.close()
        return
    _CRASH_FILE = crash_file
    try:
        faulthandler.enable(file=crash_file, all_threads=True)
    except (RuntimeError, OSError):
        pass

    sys.excepthook = lambda exc_type, exc_value, exc_tb: _write_uncaught(
        exc_type, exc_value, exc_tb, "UNCAUGHT"
    )
    if hasattr(threading, "excepthook"):
        threading.excepthook = lambda args: _write_uncaught(
            args.exc_type, args.exc_value, args.exc_traceback, "THREAD_CRASH"
        )
    atexit.register(lambda: _flush_handlers(logging.getLogger("hamlog")))
    _HOOKS_INSTALLED = True


def configure_logging(root, level="INFO", db_path=None, keep_days=30):
    log_dir = Path(root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hamlog")
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s %(message)s")
    formatter.converter = time.gmtime
    if not any(isinstance(handler, TimedRotatingFileHandler) for handler in logger.handlers):
        file_handler = TimedRotatingFileHandler(
            log_dir / "app.log", when="midnight", backupCount=max(int(keep_days), 1),
            encoding="utf-8", utc=True,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    db_handlers = [handler for handler in logger.handlers if isinstance(handler, DatabaseLogHandler)]
    if db_path and db_handlers:
        db_handlers[0].db_path = str(db_path)
    elif db_path:
        db_handler = DatabaseLogHandler(db_path)
        db_handler.setFormatter(formatter)
        logger.addHandler(db_handler)
    _install_crash_hooks((log_dir / "crash.log").open("a", encoding="utf-8"))
    return logger


def get_logger(name="hamlog"):
    return logging.getLogger(name if name == "hamlog" or name.startswith("hamlog.") else f"hamlog.{name}")
