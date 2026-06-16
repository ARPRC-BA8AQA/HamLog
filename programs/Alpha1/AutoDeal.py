# _*_coding :utf-8 _
# @Time : 2026/6/15 10:36
# @Author : C盘研究所
# @File : AutoDeal
# @Project : HamLog Project
# -*- coding: utf-8 -*-
"""
AutoDeal - 业余无线电台日志管理系统后端模块
负责数据库操作和文件处理
"""
import sqlite3
import platform
import os
from datetime import datetime
from pathlib import Path
def get_user_data_dir(app_name="HamLog"):
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", "~"))
        # print(base)
    elif system == "Darwin":
        base = Path("~/Library/Application Support")
    else:  # Linux
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
    path = base.expanduser() / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path / "Log.db"
db_path = get_user_data_dir()
db_path.touch(exist_ok=True)



class Database:
    """数据库操作类"""

    def __init__(self, db_path=db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_table()

    def _init_table(self):
        """初始化日志表"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Callsign TEXT NOT NULL,
                Freq TEXT,
                Year INTEGER,
                Month INTEGER,
                Day INTEGER,
                Time TEXT,
                Mode TEXT,
                Power_self TEXT,
                Power_side TEXT,
                Rst_self TEXT,
                Rst_side TEXT,
                QTH TEXT,
                Device TEXT,
                QSL_RX TEXT,
                QSL_SEND TEXT,
                Remarks TEXT,
                CreateTime TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add(self, log_dict):
        """
        添加一条日志记录
        :param log_dict: 字典格式日志数据
        :return: (bool, str) 成功/失败，消息
        """
        try:
            columns = ', '.join(log_dict.keys())
            placeholders = ', '.join(['?' for _ in log_dict])
            sql = f"INSERT INTO log ({columns}) VALUES ({placeholders})"
            self.cursor.execute(sql, tuple(log_dict.values()))
            self.conn.commit()
            return True, "日志添加成功"
        except Exception as e:
            return False, f"添加失败: {str(e)}"

    def delete(self, log_id):
        """删除日志"""
        try:
            self.cursor.execute("DELETE FROM log WHERE id=?", (log_id,))
            self.conn.commit()
            return True, "删除成功"
        except Exception as e:
            return False, f"删除失败: {str(e)}"

    def update(self, log_id, log_dict):
        """更新日志"""
        try:
            sets = ', '.join([f"{k}=?" for k in log_dict.keys()])
            values = list(log_dict.values()) + [log_id]
            sql = f"UPDATE log SET {sets} WHERE id=?"
            self.cursor.execute(sql, tuple(values))
            self.conn.commit()
            return True, "更新成功"
        except Exception as e:
            return False, f"更新失败: {str(e)}"

    def query(self, **kwargs):
        """
        查询日志
        :param kwargs: 查询条件，如 callsign='BA8AQA'
        :return: 日志列表
        """
        try:
            if kwargs:
                conditions = ' AND '.join([f"{k}=?" for k in kwargs.keys()])
                sql = f"SELECT * FROM log WHERE {conditions} ORDER BY Year DESC, Month DESC, Day DESC, Time DESC"
                self.cursor.execute(sql, tuple(kwargs.values()))
            else:
                self.cursor.execute("SELECT * FROM log ORDER BY Year DESC, Month DESC, Day DESC, Time DESC")
            columns = [desc[0] for desc in self.cursor.description]
            rows = self.cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return []

    def search(self, keyword):
        """模糊搜索"""
        try:
            sql = """
                SELECT * FROM log 
                WHERE Callsign LIKE ? OR QTH LIKE ? OR Device LIKE ? OR Remarks LIKE ?
                ORDER BY Year DESC, Month DESC, Day DESC, Time DESC
            """
            pattern = f"%{keyword}%"
            self.cursor.execute(sql, (pattern, pattern, pattern, pattern))
            columns = [desc[0] for desc in self.cursor.description]
            rows = self.cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return []

    def get_by_id(self, log_id):
        """通过ID获取单条日志"""
        try:
            self.cursor.execute("SELECT * FROM log WHERE id=?", (log_id,))
            columns = [desc[0] for desc in self.cursor.description]
            row = self.cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None
        except Exception as e:
            return None

    def get_all(self):
        """获取所有日志"""
        return self.query()

    def close(self):
        """关闭数据库连接"""
        self.conn.close()


class SettingsManager:
    """设置管理类"""

    def __init__(self, db_path=db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_settings_table()

    def _init_settings_table(self):
        """初始化设置表"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()
        # 设置默认值
        defaults = {
            'my_callsign': 'Your Callsign',
            'my_name': '',
            'my_qth': '',
            'my_grid': '',
            'default_mode': 'FM',
            'default_power': '5W',
            'default_device': 'Device',
            'theme': 'dark'
        }
        for k, v in defaults.items():
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()

    def get(self, key, default=None):
        """获取设置项"""
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else default

    def set(self, key, value):
        """设置项"""
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_all(self):
        """获取所有设置"""
        self.cursor.execute("SELECT key, value FROM settings")
        return dict(self.cursor.fetchall())

    def close(self):
        self.conn.close()


# 数据校验工具
class Validator:
    """输入数据校验器"""

    @staticmethod
    def validate_callsign(callsign):
        """校验呼号格式"""
        if not callsign or not callsign.strip():
            return False, "呼号不能为空"
        callsign = callsign.strip().upper()
        # 呼号格式：1-2字母前缀 + 数字 + 1-3字母后缀
        import re
        pattern = r'^[A-Z]{1,2}[0-9][A-Z]{1,3}$'
        if not re.match(pattern, callsign):
            return False, "呼号格式不正确（如：BA8AQA）"
        return True, callsign

    @staticmethod
    def validate_date(year, month, day):
        """校验日期"""
        try:
            y, m, d = int(year), int(month), int(day)
            datetime(y, m, d)
            return True, (y, m, d)
        except (ValueError, TypeError):
            return False, "日期格式不正确"

    @staticmethod
    def validate_time(time_str):
        """校验时间格式 HHMM"""
        import re
        if not time_str or not re.match(r'^[0-2][0-9][0-5][0-9]$', time_str.strip()):
            return False, "时间格式应为HHMM（如：1316）"
        h = int(time_str[:2])
        m = int(time_str[2:])
        if h > 23 or m > 59:
            return False, "时间范围不正确"
        return True, f"{h:02d}{m:02d}"

    @staticmethod
    def validate_rst(rst):
        """校验RST报告"""
        import re
        if not rst or not re.match(r'^[1-5][1-9][1-9]?$', rst.strip()):
            return False, "RST报告格式不正确（如：59, 599）"
        return True, rst.strip()

    @staticmethod
    def validate_power(power):
        """校验功率"""
        if not power or not power.strip():
            return False, "功率不能为空"
        import re
        if not re.match(r'^\d+\s*[Ww]?$', power.strip()):
            return False, "功率格式不正确（如：5W, 100W）"
        return True, power.strip().upper()

    @staticmethod
    def validate_qsl_date(date_str):
        """校验QSL日期格式 YYYYMMDD"""
        if not date_str or not date_str.strip():
            return True, ""  # 允许为空
        import re
        if not re.match(r'^\d{8}$', date_str.strip()):
            return False, "QSL日期格式应为YYYYMMDD（如：20260612）"
        y = int(date_str[:4])
        m = int(date_str[4:6])
        d = int(date_str[6:])
        try:
            datetime(y, m, d)
            return True, date_str.strip()
        except ValueError:
            return False, "QSL日期不合法"

    @staticmethod
    def validate_freq(freq):
        """校验频率"""
        if not freq or not freq.strip():
            return True, ""  # 允许为空
        import re
        # 支持 MHz 或带单位的频率
        if not re.match(r'^[0-9]+\.?[0-9]*\s*[Mm]?[Hh][Zz]?$', freq.strip()):
            return False, "频率格式不正确（如：144.000MHz）"
        return True, freq.strip().upper()


if __name__ == "__main__":
    # 测试
    db = Database()
    db.close()

