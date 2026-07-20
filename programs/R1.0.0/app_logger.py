# -*- coding: utf-8 -*-
"""
AppLogger - HamLog 软件运行日志系统
支持文件持久化、分级日志、GUI查看器
"""
import os
import sys
import logging
import logging.handlers
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from PyQt6.QtCore import QObject, pyqtSignal, QThread


class LogDatabase:
    """SQLite 日志缓存数据库，支持快速查询和过滤"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                source TEXT,
                message TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_time ON app_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_level ON app_logs(level)
        """)
        conn.commit()
        conn.close()

    def insert(self, timestamp: str, level: str, source: str, message: str):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO app_logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            (timestamp, level, source, message)
        )
        conn.commit()
        conn.close()

    def query(self, level: Optional[str] = None, keyword: Optional[str] = None,
              limit: int = 1000, offset: int = 0) -> List[Dict]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        params = []

        if level and level != "ALL":
            conditions.append("level = ?")
            params.append(level)
        if keyword:
            conditions.append("(message LIKE ? OR source LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT * FROM app_logs {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def clear_old(self, days: int = 30):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM app_logs WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT level, COUNT(*) FROM app_logs GROUP BY level")
        stats = dict(cursor.fetchall())
        cursor.execute("SELECT COUNT(*) FROM app_logs")
        total = cursor.fetchone()[0]
        conn.close()
        stats["TOTAL"] = total
        return stats


class AppLogger(QObject):
    """HamLog 应用日志主类（单例）"""

    log_recorded = pyqtSignal(str, str, str, str)  # level, source, message, timestamp

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: Optional[Path] = None):
        if AppLogger._initialized:
            return
        super().__init__()
        AppLogger._initialized = True

        if log_dir is None:
            log_dir = Path.home() / ".local" / "share" / "HamLog" / "logs"
            if sys.platform == "win32":
                log_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "HamLog" / "logs"
            elif sys.platform == "darwin":
                log_dir = Path.home() / "Library" / "Application Support" / "HamLog" / "logs"

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 文件日志（按天轮转，保留30天）
        self.file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(self.log_dir / "app.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        self.file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))

        self.logger = logging.getLogger("HamLog")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.file_handler)

        # SQLite 缓存库
        self.db = LogDatabase(self.log_dir / "logs_cache.db")

        self.info("AppLogger", "日志系统初始化完成")

    def _write(self, level: str, source: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 写入文件
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(f"[{source}] {message}")

        # 写入SQLite缓存
        self.db.insert(timestamp, level, source, message)

        # 发射信号
        self.log_recorded.emit(level, source, message, timestamp)

    def debug(self, source: str, message: str):
        self._write("DEBUG", source, message)

    def info(self, source: str, message: str):
        self._write("INFO", source, message)

    def warning(self, source: str, message: str):
        self._write("WARNING", source, message)

    def error(self, source: str, message: str):
        self._write("ERROR", source, message)

    def critical(self, source: str, message: str):
        self._write("CRITICAL", source, message)

    def query_logs(self, **kwargs) -> List[Dict]:
        return self.db.query(**kwargs)

    def get_stats(self) -> Dict:
        return self.db.get_stats()

    def clear_old_logs(self, days: int = 30):
        self.db.clear_old(days)
        self.info("AppLogger", f"已清理 {days} 天前的日志缓存")

    def get_log_file_path(self) -> Path:
        return Path(self.file_handler.baseFilename)


# 便捷函数
def get_logger() -> AppLogger:
    """获取日志单例"""
    return AppLogger()
