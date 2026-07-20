# -*- coding: utf-8 -*-
"""
HamLog Project - 自动更新模块
从 Gitee 获取版本信息，通过 ghproxy 代理下载 GitHub Release 的 Inno Setup 安装包
"""

# 更新原理：先从Gitee拉取文件，在项目Gitee仓库下有update.txt，里面有最新版版本号、安装程序的github下载链接
# 、更新日志的下载链接，更新日志是一个docx文档，force_update选项是用来设置是否强制更新此版本，其值为1是即强制更新

# 【原则上，不能使用强制更新！】
import os
import sys
import tempfile
import subprocess
import platform
import urllib.parse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import zipfile
from xml.etree import ElementTree

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QCheckBox
)


# ============================================
# 配置常量
# ============================================

GITEE_UPDATE_URL = "https://gitee.com/c-disk-research-institute/HamLog/raw/main/update.txt"

GHPROXY_MIRRORS = [
    "https://ghproxy.com/",
    "https://mirror.ghproxy.com/",
    "https://ghproxy.net/",
]

# 打包时由 CI/CD 替换为实际版本号
CURRENT_VERSION = "Release 1.0.0"


# ============================================
# 工具函数
# ============================================

def _safe_url(url: str) -> str:
    """确保 URL 中的空格和中文被正确编码，但不破坏协议头和路径结构"""
    if not url:
        return ""
    has_proxy = any(url.startswith(m) for m in GHPROXY_MIRRORS)

    if has_proxy:
        for mirror in GHPROXY_MIRRORS:
            if url.startswith(mirror):
                raw = url[len(mirror):]
                encoded = urllib.parse.quote(raw, safe=":/?#[]@!$&'()*+,;=")
                return mirror + encoded
        return url

    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=")


def _proxied_url(url: str, mirror_index: int = 0) -> str:
    """为 GitHub 链接添加代理前缀，支持多镜像"""
    if not url:
        return ""
    if any(url.startswith(m) for m in GHPROXY_MIRRORS):
        return _safe_url(url)
    if "github.com" in url or "githubusercontent.com" in url:
        mirror = GHPROXY_MIRRORS[mirror_index] if mirror_index < len(GHPROXY_MIRRORS) else ""
        return _safe_url(mirror + url)
    return _safe_url(url)


def _parse_docx_text(docx_path: str) -> str:
    """无需外部依赖，直接用 zipfile + xml 解析 .docx 文本"""
    try:
        with zipfile.ZipFile(docx_path) as zf:
            with zf.open("word/document.xml") as f:
                xml_content = f.read()

        root = ElementTree.fromstring(xml_content)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        texts = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "t" and elem.text:
                texts.append(elem.text)
            elif tag == "br":
                texts.append("\n")
            elif tag == "tab":
                texts.append("\t")
            elif tag == "p":
                texts.append("\n")

        return "".join(texts).strip()

    except Exception as e:
        return f"无法读取更新日志文档: {e}\n请访问 Gitee 仓库查看最新更新说明。"


# ============================================
# 版本信息
# ============================================

class UpdateInfo:
    """解析 update.txt"""

    def __init__(self, raw_text: str = ""):
        self.version = ""
        self.exe_url = ""           # GitHub Release assets 里的 Inno Setup EXE 直链
        self.changelog_doc_url = ""  # 远端仓库的 Word 文档直链
        self.force_update = False
        self.parse(raw_text)

    def parse(self, text: str):
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "version":
                self.version = value
            elif key == "exe_url":
                self.exe_url = value
            elif key == "changelog_doc_url":
                self.changelog_doc_url = value
            elif key == "force_update":
                self.force_update = value in ("1", "true", "yes", "on")

    @property
    def proxied_exe_url(self) -> str:
        return _proxied_url(self.exe_url)

    @property
    def proxied_changelog_url(self) -> str:
        return _proxied_url(self.changelog_doc_url)

    def is_newer(self, current_ver: str) -> bool:
        """支持 Release X.X.X 格式（统一使用 Release 前缀，含空格）"""

        def normalize(v: str) -> str:
            v = v.strip().upper()
            # 正确移除 "RELEASE " 前缀（含空格）
            if v.startswith("RELEASE "):
                v = v[8:]  # len("RELEASE ") == 8
            return v.strip()

        try:
            def to_tuple(v: str):
                parts = [p for p in v.split(".") if p.isdigit()]
                return tuple(int(x) for x in parts)

            self_norm = normalize(self.version)
            cur_norm = normalize(current_ver)
            return to_tuple(self_norm) > to_tuple(cur_norm)
        except Exception:
            # 兜底：统一格式后字符串比较
            return normalize(self.version) != normalize(current_ver)


# ============================================
# 后台线程
# ============================================

class UpdateCheckThread(QThread):
    check_finished = pyqtSignal(bool, object, str)  # (has_update, UpdateInfo, msg)

    def __init__(self, current_ver: str = CURRENT_VERSION):
        super().__init__()
        self.current_ver = current_ver

    def run(self):
        try:
            req = Request(
                GITEE_UPDATE_URL,
                headers={"User-Agent": "HamLog-Updater/1.0"},
                method="GET",
            )
            with urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            info = UpdateInfo(raw)
            if not info.version:
                self.check_finished.emit(False, None, "无法解析版本信息")
                return
            if not info.exe_url:
                self.check_finished.emit(False, None, "更新配置缺少安装包链接")
                return

            if info.is_newer(self.current_ver):
                self.check_finished.emit(True, info, f"发现新版本: {info.version}")
            else:
                self.check_finished.emit(False, None, "当前已是最新版本")

        except HTTPError as e:
            self.check_finished.emit(False, None, f"服务器错误: {e.code}")
        except URLError as e:
            self.check_finished.emit(False, None, f"网络连接失败: {e.reason}")
        except Exception as e:
            self.check_finished.emit(False, None, f"检查更新失败: {str(e)}")


class ChangelogDownloadThread(QThread):
    """下载并解析远端 Word 文档"""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".docx", prefix="hamlog_changelog_")
            os.close(fd)

            req = Request(self.url, headers={"User-Agent": "HamLog-Updater/1.0"})
            with urlopen(req, timeout=30) as resp:
                with open(temp_path, "wb") as f:
                    f.write(resp.read())

            text = _parse_docx_text(temp_path)

            try:
                os.unlink(temp_path)
            except Exception:
                pass

            self.finished_signal.emit(True, text)

        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            self.finished_signal.emit(False, str(e))


class DownloadThread(QThread):
    """文件下载线程，带多镜像自动回退"""
    progress = pyqtSignal(int)
    speed = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.original_url = url
        self.save_path = save_path
        self._running = True

    def run(self):
        import time

        for idx in range(len(GHPROXY_MIRRORS)):
            if not self._running:
                break

            url = _proxied_url(self.original_url, idx)
            try:
                req = Request(url, headers={"User-Agent": "HamLog-Updater/1.0"})
                chunk_size = 8192
                downloaded = 0
                start_time = time.time()

                with urlopen(req, timeout=120) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    with open(self.save_path, "wb") as f:
                        while self._running:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total > 0:
                                self.progress.emit(int(downloaded * 100 / total))

                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                speed = downloaded / elapsed
                                if speed > 1024 * 1024:
                                    self.speed.emit(f"{speed / 1024 / 1024:.1f} MB/s")
                                elif speed > 1024:
                                    self.speed.emit(f"{speed / 1024:.1f} KB/s")
                                else:
                                    self.speed.emit(f"{speed:.0f} B/s")

                if not self._running:
                    try:
                        os.unlink(self.save_path)
                    except Exception:
                        pass
                    self.finished_signal.emit(False, "下载已取消")
                    return

                self.finished_signal.emit(True, "下载完成")
                return

            except Exception as e:
                if idx == len(GHPROXY_MIRRORS) - 1:
                    self.finished_signal.emit(False, f"下载失败: {str(e)}")

    def stop(self):
        self._running = False


# ============================================
# 安装器（Inno Setup 专用）
# ============================================

class UpdateInstaller:
    @staticmethod
    def get_install_dir() -> str:
        """获取当前程序安装目录"""
        if getattr(sys, "frozen", False):
            return str(Path(sys.executable).parent)
        return str(Path(__file__).parent)

    @staticmethod
    def install(exe_path: str, install_dir: str = None) -> tuple:
        """执行 Inno Setup 静默覆盖安装"""
        if platform.system() != "Windows":
            return False, "自动安装仅支持 Windows 平台"

        if install_dir is None:
            install_dir = UpdateInstaller.get_install_dir()

        args = [
            exe_path,
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f'"/DIR={install_dir}"',
            "/FORCECLOSEAPPLICATIONS",
        ]

        try:
            subprocess.Popen(
                args,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
            return True, "安装程序已启动"
        except Exception as e:
            return False, f"启动安装程序失败: {e}"


# ============================================
# 更新对话框
# ============================================

class UpdateDialog(QDialog):
    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.info = update_info
        self.exe_temp_path = None
        self.download_thread = None
        self.changelog_thread = None
        self.setup_ui()
        self.load_changelog()

    def setup_ui(self):
        self.setWindowTitle(f"发现新版本 - HamLog {self.info.version}")
        self.setMinimumWidth(650)
        self.setMinimumHeight(600)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            f"<h2>🚀 HamLog {self.info.version} 可用</h2>"
            f"<p>当前版本: <b>{CURRENT_VERSION}</b></p>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel("更新日志:"))
        self.changelog_edit = QTextEdit()
        self.changelog_edit.setReadOnly(True)
        self.changelog_edit.setPlaceholderText("正在从远端仓库加载更新日志...")
        self.changelog_edit.setMinimumHeight(180)
        layout.addWidget(self.changelog_edit)

        self.status_label = QLabel("准备下载...")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.speed_label)

        self.auto_check_cb = QCheckBox("启动时自动检查更新")
        self.auto_check_cb.setChecked(True)
        layout.addWidget(self.auto_check_cb)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.later_btn = QPushButton("稍后提醒")
        self.later_btn.clicked.connect(self.reject)

        self.ignore_btn = QPushButton("忽略此版本")
        self.ignore_btn.clicked.connect(self.ignore_version)

        self.download_btn = QPushButton("⬇️ 下载并安装")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #666; }
        """)
        self.download_btn.clicked.connect(self.start_download)

        btn_layout.addWidget(self.ignore_btn)
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.download_btn)
        layout.addLayout(btn_layout)

        if self.info.force_update:
            self.later_btn.setEnabled(False)
            self.ignore_btn.setEnabled(False)
            self.status_label.setText("⚠️ 此版本为强制更新，必须安装后才能继续使用")

    def load_changelog(self):
        if not self.info.changelog_doc_url:
            self.changelog_edit.setPlainText("暂无更新日志")
            return

        self.changelog_thread = ChangelogDownloadThread(self.info.proxied_changelog_url)
        self.changelog_thread.finished_signal.connect(self.on_changelog_loaded)
        self.changelog_thread.start()

    def on_changelog_loaded(self, success: bool, text: str):
        if success:
            self.changelog_edit.setPlainText(text)
        else:
            self.changelog_edit.setPlainText(
                f"加载更新日志失败: {text}\n"
                f"文档地址: {self.info.changelog_doc_url}"
            )

    def start_download(self):
        url = self.info.proxied_exe_url
        if not url:
            QMessageBox.critical(self, "错误", "安装包下载链接无效")
            return

        fd, self.exe_temp_path = tempfile.mkstemp(suffix=".exe", prefix="hamlog_setup_")
        os.close(fd)

        self.download_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.ignore_btn.setEnabled(False)
        self.status_label.setText("正在下载安装程序...")

        self.download_thread = DownloadThread(url, self.exe_temp_path)
        self.download_thread.progress.connect(self.progress.setValue)
        self.download_thread.speed.connect(self.speed_label.setText)
        self.download_thread.finished_signal.connect(self.on_download_finished)
        self.download_thread.start()

    def on_download_finished(self, success: bool, msg: str):
        if not success:
            QMessageBox.critical(self, "下载失败", msg)
            self.download_btn.setEnabled(True)
            self.later_btn.setEnabled(True)
            self.ignore_btn.setEnabled(True)
            return

        self.status_label.setText("下载完成，正在启动安装程序...")
        self.progress.setRange(0, 0)
        self.speed_label.setText("")

        ok, msg = UpdateInstaller.install(self.exe_temp_path)
        if ok:
            if hasattr(self.parent(), "settings"):
                self.parent().settings.set(
                    "auto_check_update",
                    "1" if self.auto_check_cb.isChecked() else "0"
                )
                self.parent().settings.set("skip_version", "")

            QMessageBox.information(
                self,
                "安装程序已启动",
                "更新安装程序已启动，将自动关闭 HamLog 并覆盖安装到原目录。\n"
                "安装完成后请手动启动 HamLog。",
            )
            self.accept()
            if hasattr(self.parent(), "close"):
                self.parent().close()
            else:
                sys.exit(0)
        else:
            QMessageBox.critical(self, "安装失败", msg)
            self.download_btn.setEnabled(True)

    def ignore_version(self):
        if hasattr(self.parent(), "settings"):
            self.parent().settings.set("skip_version", self.info.version)
        self.reject()

    def closeEvent(self, event):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait(2000)
        event.accept()


# ============================================
# 更新管理器（供主窗口调用）
# ============================================

class UpdateManager:
    def __init__(self, main_window, current_ver: str = CURRENT_VERSION):
        self.main_window = main_window
        self.current_ver = current_ver
        self.check_thread = None

    def check_update(self, silent: bool = False):
        """
        检查更新
        :param silent: True=静默模式（无更新时不弹窗）
        """
        skip_ver = ""
        if hasattr(self.main_window, "settings"):
            skip_ver = self.main_window.settings.get("skip_version", "")

        self.check_thread = UpdateCheckThread(self.current_ver)
        self.check_thread.check_finished.connect(
            lambda has_update, info, msg: self._on_finished(
                has_update, info, msg, silent, skip_ver
            )
        )
        self.check_thread.start()

    def _on_finished(self, has_update, info, msg, silent, skip_ver):
        if not has_update:
            if not silent:
                QMessageBox.information(self.main_window, "检查更新", msg)
            return

        if skip_ver and info.version == skip_ver and not info.force_update:
            if not silent:
                QMessageBox.information(
                    self.main_window,
                    "检查更新",
                    f"当前已是最新版本（已忽略 {info.version}）",
                )
            return

        dialog = UpdateDialog(info, parent=self.main_window)
        dialog.exec()


def auto_check_on_startup(main_window, current_ver: str = CURRENT_VERSION):
    """程序启动时自动检查（如果设置允许）"""
    if hasattr(main_window, "settings"):
        enabled = main_window.settings.get("auto_check_update", "1") == "1"
    else:
        enabled = True

    if enabled:
        manager = UpdateManager(main_window, current_ver)
        manager.check_update(silent=True)
