# -*- coding: utf-8 -*-
"""
LoTW 上传对话框 - HTTP上传方式
流程：
1. 调用TQSL命令行将ADIF签名生成.tq8文件
2. 用HTTP POST上传.tq8到 lotw.arrl.org/lotw/upload
"""
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

# === 新增：代理支持 ===
from proxy_manager import get_proxy_manager

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QComboBox, QTextEdit, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal


# ============================================
# 1. TQSL 查找器（修复版）
# ============================================

class TQSLFinder:
    """查找 TQSL 安装位置"""

    DEFAULT_PATHS = [
        r"C:\Program Files\TrustedQSL\tqsl.exe",
        r"C:\Program Files (x86)\TrustedQSL\tqsl.exe",
        r"C:\TrustedQSL\tqsl.exe",
        r"D:\Program Files\TrustedQSL\tqsl.exe",
        r"D:\Program Files (x86)\TrustedQSL\tqsl.exe",
        r"E:\Program Files\TrustedQSL\tqsl.exe",
        r"E:\Program Files (x86)\TrustedQSL\tqsl.exe",
    ]

    TQSL_NAMES = ['tqsl.exe', 'TQSL.exe']

    @classmethod
    def find_tqsl(cls) -> str:
        """查找TQSL可执行文件路径"""
        # 1. 默认路径
        for path in cls.DEFAULT_PATHS:
            if os.path.isfile(path):
                return path

        # 2. PATH环境变量
        try:
            result = subprocess.run(
                ["tqsl", "--version"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return "tqsl"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 3. 搜索所有驱动器
        for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                found = cls._search_drive(drive)
                if found:
                    return found

        return None

    @classmethod
    def _search_drive(cls, drive: str) -> str:
        priority_dirs = [
            'Program Files', 'Program Files (x86)', 'TrustedQSL',
            'Software', 'Apps', 'Applications', 'HamRadio',
        ]
        for dirname in priority_dirs:
            target = os.path.join(drive, dirname)
            if os.path.isdir(target):
                found = cls._search_directory(target)
                if found:
                    return found
        return cls._search_directory(drive, max_depth=3)

    @classmethod
    def _search_directory(cls, root: str, max_depth: int = 5) -> str:
        skip_dirs = {
            'windows', 'programdata', '$recycle.bin', 'system volume information',
            'temp', 'tmp', 'cache', 'logs', 'drivers', 'syswow64',
        }
        for current_root, dirs, files in os.walk(root):
            depth = current_root[len(root):].count(os.sep)
            if depth > max_depth:
                del dirs[:]
                continue
            dirs[:] = [d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]
            for name in cls.TQSL_NAMES:
                if name in files:
                    return os.path.join(current_root, name)
        return None

    @classmethod
    def get_version(cls, tqsl_path: str) -> str:
        if not tqsl_path:
            return None
        try:
            result = subprocess.run(
                [tqsl_path, "-x", "--version"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                match = re.search(r'V?(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None


# ============================================
# 2. 证书查找器（从文件系统）- 修复版
# ============================================

class TQSLCertFinder:
    """查找TQSL证书"""

    @classmethod
    def find_certificates(cls) -> list:
        certs = []
        paths = [
            Path(os.environ.get('APPDATA', '')) / 'TrustedQSL' / 'keys',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'TrustedQSL' / 'keys',
            Path.home() / 'AppData' / 'Roaming' / 'TrustedQSL' / 'keys',
        ]
        for keys_dir in paths:
            if not keys_dir.exists():
                continue
            for cert_file in keys_dir.iterdir():
                if cert_file.is_file() and not cert_file.name.startswith('.'):
                    try:
                        with open(cert_file, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()

                        # 修复：支持多种 CALLSIGN 字段格式
                        # 格式1: <CALLSIGN:6>BA8AQA
                        # 格式2: <CALLSIGN:6> BA8AQA
                        m = re.search(r'<CALLSIGN:(\d+)>\s*([^<\n\r]+)', content)
                        if m:
                            callsign = m.group(2).strip()
                            # 获取 DXCC 实体
                            m_dxcc = re.search(r'<TQSL_CRQ_DXCC_ENTITY:(\d+)>\s*([^<\n\r]+)', content)
                            dxcc = m_dxcc.group(2).strip() if m_dxcc else ""
                            # 获取 QSO 起始日期
                            m_date = re.search(r'<TQSL_CRQ_QSO_NOT_BEFORE:(\d+)>\s*(\d{4}-\d{2}-\d{2})', content)
                            qso_not_before = m_date.group(2) if m_date else ""

                            certs.append({
                                'callsign': callsign,
                                'dxcc': dxcc,
                                'path': str(cert_file),
                                'name': cert_file.name,
                                'qso_not_before': qso_not_before
                            })
                    except Exception:
                        pass
        return certs

    @classmethod
    def get_station_locations(cls) -> list:
        """从TQSL配置文件读取台站位置"""
        locations = ['Default']
        config_paths = [
            Path(os.environ.get('APPDATA', '')) / 'TrustedQSL' / 'tqslconfig.xml',
            Path.home() / 'AppData' / 'Roaming' / 'TrustedQSL' / 'tqslconfig.xml',
        ]
        for config_file in config_paths:
            if config_file.exists():
                try:
                    tree = ET.parse(config_file)
                    root = tree.getroot()
                    for loc in root.iter('location'):
                        name = loc.get('name', '')
                        if name and name not in locations:
                            locations.append(name)
                except Exception:
                    pass
        return locations


# ============================================
# 3. LoTW 上传线程 - 修复版
# ============================================

class LoTWUploadThread(QThread):
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, adi_path: str, tqsl_path: str, station_loc: str = None,
                 duplicate_action: str = "compliant", cert_callsign: str = None):
        super().__init__()
        self.adi_path = adi_path
        self.tqsl_path = tqsl_path
        self.station_loc = station_loc
        self.duplicate_action = duplicate_action
        self.cert_callsign = cert_callsign

    def run(self):
        try:
            # 1. 用TQSL签名生成.tq8文件
            self.progress.emit("正在用TQSL签名...")
            tq8_path = self._sign_with_tqsl()
            if not tq8_path:
                return

            # 2. 用HTTP上传.tq8文件
            self.progress.emit("正在上传到LoTW服务器...")
            result = self._upload_tq8(tq8_path)
            self.finished_signal.emit(result)

            # 清理临时文件
            try:
                os.unlink(tq8_path)
            except:
                pass

        except Exception as e:
            self.finished_signal.emit({
                'status': 'error',
                'message': f"上传异常: {str(e)}"
            })

    def _sign_with_tqsl(self) -> str:
        """调用TQSL签名生成.tq8文件"""
        # 创建临时.tq8文件
        fd, tq8_path = tempfile.mkstemp(suffix='.tq8')
        os.close(fd)

        cmd = [
            self.tqsl_path,
            "-x",  # batch模式
            "-d",  # 不弹出日期对话框
            "-a", self.duplicate_action,
            "-o", tq8_path,  # 输出到临时文件
        ]

        # 修复：台站位置处理
        if self.station_loc and self.station_loc not in ("Default", "默认位置 (Default)"):
            cmd.extend(["-l", self.station_loc])

        # 修复：-c 参数用于指定呼号证书
        if self.cert_callsign:
            cmd.extend(["-c", self.cert_callsign])

        cmd.append(self.adi_path)

        self.progress.emit(f"TQSL命令: {' '.join(cmd)}")

        try:
            # 修复：捕获 stdout 和 stderr 到临时文件以便分析
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            output = (result.stdout or "") + "\n" + (result.stderr or "")
            self.progress.emit(f"TQSL输出:\n{output[:500]}")

            # 检查是否成功生成文件
            if os.path.exists(tq8_path) and os.path.getsize(tq8_path) > 0:
                self.progress.emit(f"签名成功，生成.tq8文件 ({os.path.getsize(tq8_path)} bytes)")
                return tq8_path

            # 没有生成文件，分析错误
            error_msg = self._parse_tqsl_error(output)

            # 修复：处理错误码 8（所有 QSO 都是重复项或超出日期范围）
            if "No QSOs to upload(8)" in output or "Final Status: No QSOs to upload (8)" in output:
                error_msg = "所有 QSO 都是重复项或超出证书日期范围。证书有效期可能从 2025-08-22 开始，请检查 QSO 日期。"

            self.finished_signal.emit({
                'status': 'sign_failed',
                'message': f"签名失败: {error_msg}"
            })
            return None

        except subprocess.TimeoutExpired:
            self.finished_signal.emit({
                'status': 'sign_failed',
                'message': "TQSL签名超时"
            })
            return None
        except Exception as e:
            self.finished_signal.emit({
                'status': 'sign_failed',
                'message': f"TQSL执行错误: {str(e)}"
            })
            return None

    def _parse_tqsl_error(self, output: str) -> str:
        """解析TQSL错误输出"""
        lines = [l.strip() for l in output.split('\n') if l.strip()]

        # 优先查找 Final Status 行
        for line in lines:
            if "Final Status:" in line:
                return line

        error_lines = [l for l in lines if any(k in l.lower() for k in ['error', 'fail', 'invalid', 'rejected'])]
        if error_lines:
            return error_lines[-1]
        if lines:
            return lines[-1]
        return "未知错误"

    def _upload_tq8(self, tq8_path: str) -> dict:
        """通过HTTP POST上传.tq8文件到LoTW"""
        upload_url = "https://lotw.arrl.org/lotw/upload"

        # 读取.tq8文件
        with open(tq8_path, 'rb') as f:
            tq8_data = f.read()

        # 构建multipart/form-data
        boundary = '----WebKitFormBoundary' + os.urandom(16).hex()

        # 修复：确保头部和正文之间有空行（\r\n\r\n）
        body_text = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="upfile"; filename="upload.tq8"\r\n'
            f'Content-Type: application/octet-stream\r\n'
            f'\r\n'
        ).encode('utf-8')

        body_end = f'\r\n--{boundary}--\r\n'.encode('utf-8')
        body = body_text + tq8_data + body_end

        try:
            req = Request(
                upload_url,
                data=body,
                headers={
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'User-Agent': 'TQSL/2.7.4 (Windows; en)',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                method='POST'
            )

            # === 新增：应用代理 ===
            proxy_mgr = get_proxy_manager()
            if proxy_mgr.is_enabled():
                self.progress.emit("使用代理上传...")

            with urlopen(req, timeout=120) as response:
                resp_text = response.read().decode('utf-8', errors='replace')
                return self._parse_upload_response(resp_text)

        except URLError as e:
            return {
                'status': 'network_error',
                'message': f"网络错误: {str(e)}"
            }
        except Exception as e:
            return {
                'status': 'upload_failed',
                'message': f"上传失败: {str(e)}"
            }

    def _parse_upload_response(self, resp_text: str) -> dict:
        """解析LoTW上传响应"""
        result = {
            'status': 'success',
            'message': '',
            'qso_count': 0,
            'uploaded_count': 0,
            'duplicate_count': 0,
            'error_count': 0
        }

        # 查找.UPL.注释
        upl_match = re.search(r'<!-- \.UPL\.\s*(\w+)\s*-->', resp_text, re.IGNORECASE)
        upl_msg_match = re.search(r'<!-- \.UPLMESSAGE\.\s*(.*?)\s*-->', resp_text, re.DOTALL | re.IGNORECASE)

        if upl_match:
            upl_result = upl_match.group(1).lower()
            if upl_result == 'accepted':
                result['status'] = 'success'
                result['message'] = "上传成功"
            else:
                result['status'] = 'upload_failed'
                result['message'] = f"服务器拒绝: {upl_result}"

        if upl_msg_match:
            msg = upl_msg_match.group(1).strip()
            if msg:
                result['message'] += f" - {msg}"

        # 如果没有找到注释，检查其他成功标志
        if not upl_match:
            if 'accepted' in resp_text.lower() or 'success' in resp_text.lower():
                result['status'] = 'success'
                result['message'] = "上传成功"
            elif 'rejected' in resp_text.lower() or 'error' in resp_text.lower():
                result['status'] = 'upload_failed'
                result['message'] = f"服务器拒绝: {resp_text[:200]}"
            else:
                result['message'] = f"服务器响应: {resp_text[:300]}"

        return result


# ============================================
# 4. 上传对话框（修复UI）
# ============================================

class LoTWUploadDialog(QDialog):
    """LoTW上传对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.uploader_thread = None
        self.tqsl_path = None
        self.certificates = []
        self.setup_ui()
        self.check_tqsl()

    def setup_ui(self):
        self.setWindowTitle("上传到 LoTW")
        self.setMinimumWidth(650)
        self.setMinimumHeight(800)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # === 文件选择 ===
        file_group = QGroupBox("选择 ADIF 文件")
        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)

        self.txt_adi_path = QLineEdit()
        self.txt_adi_path.setPlaceholderText("请选择要上传的 .adi 文件")

        self.btn_browse_adi = QPushButton("浏览...")
        self.btn_browse_adi.setFixedWidth(70)
        self.btn_browse_adi.clicked.connect(self.browse_adi)

        file_layout.addWidget(self.txt_adi_path, stretch=1)
        file_layout.addWidget(self.btn_browse_adi)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # === TQSL 状态 ===
        self.tqsl_group = QGroupBox("TQSL 状态")
        tqsl_layout = QFormLayout()
        tqsl_layout.setSpacing(8)

        self.lbl_tqsl_path = QLabel("未检测")
        self.lbl_tqsl_version = QLabel("-")
        self.lbl_cert_status = QLabel("未知")

        tqsl_layout.addRow("TQSL 路径:", self.lbl_tqsl_path)
        tqsl_layout.addRow("版本:", self.lbl_tqsl_version)
        tqsl_layout.addRow("证书状态:", self.lbl_cert_status)

        self.btn_check_tqsl = QPushButton("重新检测")
        self.btn_check_tqsl.clicked.connect(self.check_tqsl)
        tqsl_layout.addRow(self.btn_check_tqsl)

        self.btn_browse_tqsl = QPushButton("手动指定 TQSL 路径")
        self.btn_browse_tqsl.clicked.connect(self.browse_tqsl)
        tqsl_layout.addRow(self.btn_browse_tqsl)

        self.tqsl_group.setLayout(tqsl_layout)
        layout.addWidget(self.tqsl_group)

        # === 上传选项 ===
        options_group = QGroupBox("上传选项")
        options_layout = QFormLayout()
        options_layout.setSpacing(8)

        self.cmb_station_loc = QComboBox()
        self.cmb_station_loc.addItem("默认位置 (Default)")
        self.cmb_station_loc.addItem("添加新位置...")
        options_layout.addRow("台站位置:", self.cmb_station_loc)

        self.cmb_duplicate = QComboBox()
        self.cmb_duplicate.addItem("跳过已上传的 (compliant)", "compliant")
        self.cmb_duplicate.addItem("全部重新上传 (all)", "all")
        self.cmb_duplicate.addItem("遇到错误停止 (abort)", "abort")
        options_layout.addRow("重复处理:", self.cmb_duplicate)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # === 日志输出 ===
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("上传日志将显示在这里...")
        self.txt_log.setMaximumHeight(120)
        layout.addWidget(QLabel("上传日志:"))
        layout.addWidget(self.txt_log)

        # === 进度条 ===
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # === 按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_upload = QPushButton("上传到 LoTW")
        self.btn_upload.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
                min-width: 100px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_upload.clicked.connect(self.upload_to_lotw)

        self.btn_close = QPushButton("关闭")
        self.btn_close.setMinimumWidth(70)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def browse_adi(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 ADIF 文件",
            str(Path.home() / "Desktop"),
            "ADI Files (*.adi *.adif);;All Files (*)"
        )
        if file_path:
            self.txt_adi_path.setText(file_path)

    def check_tqsl(self):
        self.tqsl_path = TQSLFinder.find_tqsl()

        if self.tqsl_path:
            self.lbl_tqsl_path.setText(self.tqsl_path)
            self.lbl_tqsl_path.setStyleSheet("color: green;")

            version = TQSLFinder.get_version(self.tqsl_path)
            self.lbl_tqsl_version.setText(version or "未知")

            self.check_certificates()
            self.load_station_locations()
            self.btn_upload.setEnabled(True)
        else:
            self.lbl_tqsl_path.setText("未找到 TQSL")
            self.lbl_tqsl_path.setStyleSheet("color: red;")
            self.lbl_tqsl_version.setText("-")
            self.lbl_cert_status.setText("请先安装 TQSL")
            self.lbl_cert_status.setStyleSheet("color: red;")
            self.btn_upload.setEnabled(False)

    def check_certificates(self):
        self.certificates = TQSLCertFinder.find_certificates()
        if self.certificates:
            cert_info = f"已配置 {len(self.certificates)} 个证书"
            for cert in self.certificates:
                cert_info += f"\n  {cert['callsign']}"
                if cert.get('qso_not_before'):
                    cert_info += f" (有效期从 {cert['qso_not_before']})"
            self.lbl_cert_status.setText(cert_info)
            self.lbl_cert_status.setStyleSheet("color: green;")
        else:
            self.lbl_cert_status.setText("未找到证书")
            self.lbl_cert_status.setStyleSheet("color: orange;")

    def load_station_locations(self):
        locations = TQSLCertFinder.get_station_locations()
        self.cmb_station_loc.clear()
        for loc in locations:
            self.cmb_station_loc.addItem(loc)
        self.cmb_station_loc.addItem("添加新位置...")

    def browse_tqsl(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 TQSL 可执行文件",
            "C:\\" if os.path.exists("C:\\") else str(Path.home()),
            "TQSL (tqsl.exe);;所有文件 (*.*)"
        )
        if file_path and os.path.isfile(file_path):
            version = TQSLFinder.get_version(file_path)
            if version:
                self.tqsl_path = file_path
                self.lbl_tqsl_path.setText(file_path)
                self.lbl_tqsl_version.setText(version)
                self.lbl_tqsl_path.setStyleSheet("color: green;")
                self.btn_upload.setEnabled(True)
                self.check_certificates()
                self.load_station_locations()
            else:
                QMessageBox.warning(self, "无效文件", "选择的文件不是有效的 TQSL 可执行文件")

    def upload_to_lotw(self):
        adi_path = self.txt_adi_path.text().strip()

        if not adi_path:
            QMessageBox.warning(self, "提示", "请先选择 ADIF 文件")
            return
        if not os.path.isfile(adi_path):
            QMessageBox.warning(self, "错误", "选择的文件不存在")
            return
        if not self.tqsl_path:
            QMessageBox.warning(self, "错误", "未找到 TQSL，无法签名")
            return

        station_loc = None
        if self.cmb_station_loc.currentIndex() >= 0:
            loc_text = self.cmb_station_loc.currentText()
            if loc_text not in ("添加新位置...", "默认位置 (Default)", "Default"):
                station_loc = loc_text

        cert_callsign = None
        if self.certificates:
            cert_callsign = self.certificates[0]['callsign']

        duplicate_action = self.cmb_duplicate.currentData()

        self.uploader_thread = LoTWUploadThread(
            adi_path, self.tqsl_path,
            station_loc=station_loc,
            duplicate_action=duplicate_action,
            cert_callsign=cert_callsign
        )
        self.uploader_thread.progress.connect(self.log)
        self.uploader_thread.finished_signal.connect(self.on_upload_finished)

        self.progress.setVisible(True)
        self.btn_upload.setEnabled(False)
        self.uploader_thread.start()

    def on_upload_finished(self, result: dict):
        self.progress.setVisible(False)
        self.btn_upload.setEnabled(True)

        self.log(f"结果: {result.get('message', '')}")

        status = result.get('status', 'error')
        if status == 'success':
            QMessageBox.information(self, "上传成功", result.get('message', '上传成功'))
        elif status == 'sign_failed':
            QMessageBox.warning(self, "签名失败", result.get('message', '签名失败'))
        elif status == 'network_error':
            QMessageBox.critical(self, "网络错误", result.get('message', '网络错误'))
        else:
            QMessageBox.critical(self, "上传失败", result.get('message', '上传失败'))

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f"[{timestamp}] {message}")


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = LoTWUploadDialog()
    dialog.show()
    sys.exit(app.exec())