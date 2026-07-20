# -*- coding: utf-8 -*-
"""
ADIF 导出和 LoTW 上传支持模块
"""
import os
import platform
import re
import sqlite3
import string
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal


# ============================================
# 1. LoTW ADI 导出器
# ============================================

class LoTWADIExporter:
    """
    适配 LoTW 的 ADIF 导出器
    严格遵循 ARRL LoTW 的字段要求
    """

    # 频率到波段的映射（MHz）
    FREQ_BAND_MAP = [
        (1.8, 2.0, '160m'), (3.5, 4.0, '80m'), (5.0, 5.5, '60m'),
        (7.0, 7.3, '40m'), (10.0, 10.15, '30m'), (14.0, 14.35, '20m'),
        (18.0, 18.17, '17m'), (21.0, 21.45, '15m'), (24.0, 24.99, '12m'),
        (28.0, 29.7, '10m'), (50.0, 54.0, '6m'), (144.0, 148.0, '2m'),
        (420.0, 450.0, '70cm'),
    ]

    # LoTW 支持的模式（部分常见模式）
    VALID_MODES = {
        'AM', 'CW', 'FM', 'SSB', 'USB', 'LSB', 'RTTY', 'PSK', 'PSK31',
        'FT8', 'FT4', 'JT65', 'JT9', 'JS8', 'MFSK', 'OLIVIA', 'CONTESTI',
        'HELL', 'HELL80', 'FELDHELL', 'PSK63', 'PSK125', 'RTTYM', 'DOMINO',
        'THOR', 'THRB', 'THRBX', 'CONTESTIA', 'MT63', 'PACKET', 'PACTOR',
        'ARDOP', 'VARA', 'FST4', 'FST4W', 'ISCAT', 'MSK144', 'Q65', 'WSPR',
    }

    def __init__(self, db_path: str, station_callsign: str = None):
        self.db_path = db_path
        self.station_callsign = station_callsign

    def _format_field(self, name: str, value) -> str:
        if value is None or value == '':
            return ''
        value_str = str(value)
        return f"<{name}:{len(value_str)}>{value_str}"

    def _freq_to_band(self, freq_mhz: float) -> str:
        if freq_mhz > 1000:
            freq_mhz = freq_mhz / 1000.0
        for low, high, band in self.FREQ_BAND_MAP:
            if low <= freq_mhz <= high:
                return band
        return ''

    def _normalize_mode(self, mode: str) -> str:
        if not mode:
            return ''
        mode_upper = mode.upper().strip()
        if mode_upper in self.VALID_MODES:
            return mode_upper
        aliases = {'PHONE': 'SSB', 'VOICE': 'SSB', 'DIGITAL': 'RTTY', 'PSK': 'PSK31'}
        return aliases.get(mode_upper, mode_upper)

    def _build_qso_date(self, year, month, day) -> str:
        try:
            return f"{int(year):04d}{int(month):02d}{int(day):02d}"
        except (ValueError, TypeError):
            return ''

    def _build_time_on(self, time_val) -> str:
        if not time_val:
            return ''
        time_str = str(time_val).strip().replace(':', '')
        if time_str.isdigit():
            if len(time_str) == 4:
                return time_str
            elif len(time_str) == 6:
                return time_str
        try:
            for fmt in ['%H:%M', '%H:%M:%S', '%H%M', '%H%M%S']:
                try:
                    t = datetime.strptime(time_str, fmt)
                    return t.strftime('%H%M%S') if 'S' in fmt else t.strftime('%H%M')
                except ValueError:
                    continue
        except:
            pass
        digits = ''.join(c for c in time_str if c.isdigit())
        return digits[:4] if len(digits) >= 4 else digits.zfill(4)

    def _build_record(self, row: dict) -> str:
        fields = []

        # CALL
        call = str(row.get('Callsign', '')).strip().upper()
        if call:
            fields.append(self._format_field('CALL', call))

        # QSO_DATE
        qso_date = self._build_qso_date(row.get('Year'), row.get('Month'), row.get('Day'))
        if qso_date:
            fields.append(self._format_field('QSO_DATE', qso_date))

        # TIME_ON
        time_on = self._build_time_on(row.get('Time'))
        if time_on:
            fields.append(self._format_field('TIME_ON', time_on))

        # BAND & FREQ
        freq = row.get('Freq')
        if freq:
            try:
                freq_str = str(freq).strip().upper()

                # 波段别名映射（处理如 "2M" 这类简写）
                BAND_ALIASES = {
                    '160M': 1.9, '80M': 3.5, '60M': 5.3, '40M': 7.0, '30M': 10.1,
                    '20M': 14.0, '17M': 18.1, '15M': 21.0, '12M': 24.9, '10M': 28.0,
                    '6M': 50.0, '4M': 70.0, '2M': 144.0, '1.25M': 222.0,
                    '70CM': 430.0, '33CM': 902.0, '23CM': 1240.0,
                }

                if freq_str in BAND_ALIASES:
                    freq_mhz = BAND_ALIASES[freq_str]
                else:
                    # 提取数字和小数点，去除所有其他字符（包括单位、空格）
                    freq_clean = re.sub(r'[^\d.]', '', freq_str)
                    if not freq_clean:
                        raise ValueError("无法解析频率")
                    freq_mhz = float(freq_clean)
                    if freq_mhz > 1000:
                        freq_mhz = freq_mhz / 1000.0

                band = self._freq_to_band(freq_mhz)
                if band:
                    fields.append(self._format_field('BAND', band))
                if freq_mhz > 0:
                    fields.append(self._format_field('FREQ', f"{freq_mhz:.5f}"))
            except (ValueError, TypeError):
                pass

        # MODE
        mode = self._normalize_mode(row.get('Mode'))
        if mode:
            fields.append(self._format_field('MODE', mode))

        # STATION_CALLSIGN
        if self.station_callsign:
            fields.append(self._format_field('STATION_CALLSIGN', self.station_callsign.upper()))

        fields.append('<eor>')
        return ''.join(fields)

    def _generate_header(self, program_name: str = "HamLog Project") -> str:
        now = datetime.now(timezone.utc)
        header = [
            f"ADIF Export from {program_name} for LoTW",
            f"<adif_ver:5>3.1.5",
            f"<programid:{len(program_name)}>{program_name}",
            f"<createdate:8>{now.strftime('%Y%m%d')}",
            "<eoh>",
            ""
        ]
        return '\n'.join(header)

    def export(self, output_path: str, query: str = None, params: tuple = None) -> dict:
        # 默认查询使用正确的表名 "log"
        if query is None:
            query = """
                SELECT Callsign, Freq, Year, Month, Day, Time, Mode,
                       Power_self, Power_side, Rst_self, Rst_side,
                       QTH, Device, QSL_RX, QSL_SEND, Remarks
                FROM log
                ORDER BY Year, Month, Day, Time
            """

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = {'total': 0, 'exported': 0, 'skipped': 0, 'errors': []}

        try:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            result['total'] = len(rows)

            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                f.write(self._generate_header())
                for row in rows:
                    record_str = self._build_record(dict(row))
                    f.write(record_str + '\n')
                    result['exported'] += 1

            return result
        finally:
            conn.close()


# ============================================
# 2. TQSL 查找器
# ============================================

class TQSLFinder:
    """查找 TQSL 安装位置（支持多驱动器搜索）"""

    DEFAULT_PATHS = {
        'Windows': [
            r"C:\Program Files\TrustedQSL\tqsl.exe",
            r"C:\Program Files (x86)\TrustedQSL\tqsl.exe",
            r"C:\TrustedQSL\tqsl.exe",
        ],
        'Darwin': [
            "/Applications/TrustedQSL.app/Contents/MacOS/tqsl",
            "/usr/local/bin/tqsl",
        ],
        'Linux': [
            "/usr/bin/tqsl",
            "/usr/local/bin/tqsl",
            "/opt/tqsl/bin/tqsl",
        ]
    }

    TQSL_NAMES = ['tqsl.exe', 'TQSL.exe']

    @classmethod
    def find_tqsl(cls, search_drives: List[str] = None) -> Optional[str]:
        system = platform.system()

        # 1. 默认路径
        for path in cls.DEFAULT_PATHS.get(system, []):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        # 2. PATH 环境变量
        try:
            result = subprocess.run(
                ["tqsl", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "tqsl"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 3. 搜索指定驱动器
        if system == 'Windows' and search_drives:
            for drive in search_drives:
                found = cls._search_drive(drive)
                if found:
                    return found

        return None

    @classmethod
    def _search_drive(cls, drive_letter: str) -> Optional[str]:
        drive = f"{drive_letter.upper()}:\\"
        if not os.path.exists(drive):
            return None

        priority_dirs = [
            'Program Files', 'Program Files (x86)', 'TrustedQSL',
            'Software', 'Apps', 'Applications', 'HamRadio', '业余无线电',
        ]

        for dirname in priority_dirs:
            target = os.path.join(drive, dirname)
            if os.path.isdir(target):
                found = cls._search_directory(target)
                if found:
                    return found

        return cls._search_directory(drive, max_depth=4)

    @classmethod
    def _search_directory(cls, root: str, max_depth: int = 6) -> Optional[str]:
        skip_dirs = {
            'windows', 'programdata', '$recycle.bin', 'system volume information',
            'temp', 'tmp', 'cache', 'logs', 'drivers', 'syswow64',
            'installer', 'winsxs', 'microsoft.net',
        }

        for current_root, dirs, files in os.walk(root):
            depth = current_root[len(root):].count(os.sep)
            if depth > max_depth:
                del dirs[:]
                continue

            dirs[:] = [d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]

            for name in cls.TQSL_NAMES:
                if name in files:
                    full_path = os.path.join(current_root, name)
                    if os.access(full_path, os.X_OK):
                        return full_path

        return None

    @classmethod
    def get_version(cls, tqsl_path: str) -> Optional[str]:
        if tqsl_path == "tqsl":
            tqsl_path = "tqsl"
        try:
            # 先尝试 -x --version 避免 GUI
            result = subprocess.run(
                [tqsl_path, "-x", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                match = re.search(r'V?(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
            # 回退到普通 --version
            result = subprocess.run(
                [tqsl_path, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                match = re.search(r'V?(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None


# ============================================
# 3. LoTW 上传线程
# ============================================

class LoTWStatus(Enum):
    SUCCESS = "success"
    ALREADY_UPLOADED = "already_uploaded"
    ERROR = "error"
    TQSL_NOT_FOUND = "tqsl_not_found"
    CERT_NOT_FOUND = "cert_not_found"
    SIGN_FAILED = "sign_failed"
    UPLOAD_FAILED = "upload_failed"


@dataclass
class LoTWResult:
    status: LoTWStatus
    message: str
    qso_count: int = 0
    uploaded_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    lotw_url: str = ""


class LoTWUploader(QThread):
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(LoTWResult)

    def __init__(self, adi_path: str, station_location: str = None,
                 upload_flags: dict = None):
        super().__init__()
        self.adi_path = adi_path
        self.station_location = station_location
        self.upload_flags = upload_flags or {}
        self.tqsl_path = None

    def run(self):
        self.tqsl_path = TQSLFinder.find_tqsl()
        if not self.tqsl_path:
            self.finished_signal.emit(LoTWResult(
                status=LoTWStatus.TQSL_NOT_FOUND,
                message="未找到 TQSL，请先安装并配置证书",
                lotw_url="https://lotw.arrl.org/lotw-help/installation/"
            ))
            return

        self.progress.emit(f"找到 TQSL: {self.tqsl_path}")

        cmd = self._build_command()
        self.progress.emit(f"执行: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=120
            )
            lotw_result = self._parse_output(result)
            self.finished_signal.emit(lotw_result)
        except subprocess.TimeoutExpired:
            self.finished_signal.emit(LoTWResult(
                status=LoTWStatus.UPLOAD_FAILED,
                message="上传超时，请检查网络连接"
            ))
        except Exception as e:
            self.finished_signal.emit(LoTWResult(
                status=LoTWStatus.ERROR,
                message=f"执行异常: {str(e)}"
            ))

    def _build_command(self) -> List[str]:
        # -x: batch 模式，不弹出 GUI 对话框
        cmd = [self.tqsl_path, "-x", "-u", "-d"]
        action = self.upload_flags.get('duplicate_action', 'compliant')
        cmd.extend(["-a", action])

        if self.station_location:
            cmd.extend(["-l", self.station_location])

        cmd.append(self.adi_path)
        return cmd

    def _parse_output(self, result: subprocess.CompletedProcess) -> LoTWResult:
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = stdout + "\n" + stderr

        if result.returncode == 0:
            qso_total = self._extract_count(combined, r'(\d+)\s+QSOs? processed')
            qso_uploaded = self._extract_count(combined, r'(\d+)\s+QSOs? uploaded')
            qso_duplicates = self._extract_count(combined, r'(\d+)\s+duplicate')
            qso_errors = self._extract_count(combined, r'(\d+)\s+error')

            if qso_uploaded > 0 and qso_errors == 0:
                status = LoTWStatus.SUCCESS
                message = f"成功上传 {qso_uploaded} 条 QSO"
            elif qso_duplicates > 0 and qso_errors == 0:
                status = LoTWStatus.ALREADY_UPLOADED
                message = f"{qso_duplicates} 条已存在，{qso_uploaded} 条新上传"
            else:
                status = LoTWStatus.SUCCESS
                message = f"处理 {qso_total} 条，上传 {qso_uploaded} 条，错误 {qso_errors} 条"

            return LoTWResult(
                status=status, message=message,
                qso_count=qso_total, uploaded_count=qso_uploaded,
                duplicate_count=qso_duplicates, error_count=qso_errors,
                lotw_url="https://lotw.arrl.org/lotwuser/default"
            )

        error_msg = self._parse_error(combined)

        if "certificate" in combined.lower() or "cert" in combined.lower():
            return LoTWResult(
                status=LoTWStatus.CERT_NOT_FOUND,
                message=f"证书错误: {error_msg}",
                lotw_url="https://lotw.arrl.org/lotwuser/default"
            )

        if "sign" in combined.lower():
            return LoTWResult(
                status=LoTWStatus.SIGN_FAILED,
                message=f"签名失败: {error_msg}"
            )

        return LoTWResult(
            status=LoTWStatus.UPLOAD_FAILED,
            message=f"上传失败: {error_msg}"
        )

    def _extract_count(self, text: str, pattern: str) -> int:
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _parse_error(self, text: str) -> str:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        error_lines = [
            l for l in lines
            if not any(kw in l.lower() for kw in ['trustedqsl', 'version', 'copyright', 'opening'])
        ]
        return error_lines[-1] if error_lines else "未知错误"