# -*- coding: utf-8 -*-
"""
HAMLOG GUI - 业余无线电台日志管理系统前端界面
使用 PyQt6 构建
"""
import pkgutil  # PyInstaller: 强制收集，防止打包后缺失
import sys
import re
import platform
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QMessageBox, QComboBox, QSpinBox, QGroupBox, QGridLayout,
    QHeaderView, QFrame, QMenu, QMenuBar, QStatusBar, QFormLayout,
    QCheckBox, QListWidget, QInputDialog, QPlainTextEdit
)
from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QAction, QKeySequence, QDesktopServices

from ADIF_Export_Dialog import ADIFExportDialog
from LoTW_Upload_Dialog import LoTWUploadDialog
from QRZ_Lookup_Dialog import QRZLookupDialog
from AutoDeal import Database, SettingsManager
from pathlib import Path
from intertime import get_ping_time
from update_module import UpdateManager, auto_check_on_startup, CURRENT_VERSION

# === 新增模块导入 ===
from app_logger import get_logger
from proxy_manager import get_proxy_manager
from font_manager import FontManager, load_font_settings
from log_viewer_dialog import LogViewerDialog
from proxy_settings_dialog import ProxySettingsDialog
from font_settings_dialog import FontSettingsDialog

# ========== 窗口材质效果 (PyQt-Frameless-Window) ==========
HAS_FRAMELESS = False
FramelessWindow = QMainWindow
_WindowEffect = None

try:
    from qframelesswindow import FramelessWindow as _FramelessWindow
    try:
        from qframelesswindow.windows.window_effect import WindowsWindowEffect as _WindowEffect
    except ImportError:
        from qframelesswindow.windows.window_effect import WindowEffect as _WindowEffect

    # 关键修复：检测 FramelessWindow 是否真正具备 QMainWindow 的能力
    if hasattr(_FramelessWindow, "setCentralWidget"):
        FramelessWindow = _FramelessWindow
        HAS_FRAMELESS = True
    else:
        print("[HamLog] qframelesswindow.FramelessWindow 缺少 setCentralWidget，回退到标准 QMainWindow")
        FramelessWindow = QMainWindow
except ImportError as e:
    print(f"[HamLog] PyQt6-Frameless-Window 未安装: {e}")
    print("[HamLog] 窗口材质效果不可用，请运行: pip install PyQt6-Frameless-Window")
    FramelessWindow = QMainWindow
except Exception as e:
    print(f"[HamLog] PyQt6-Frameless-Window 导入失败: {e}")
    print("[HamLog] 窗口材质效果不可用")
    FramelessWindow = QMainWindow


class StyleSheet:
    """样式表"""
    DARK = """
    QMainWindow { background-color: #1e1e1e; }
    QWidget { background-color: #1e1e1e; color: #e0e0e0; }
    QGroupBox { border: 1px solid #3c3c3c; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #4fc3f7; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit, QPlainTextEdit {
        background-color: #2d2d2d; border: 1px solid #3c3c3c; border-radius: 4px; padding: 6px 10px; color: #e0e0e0; selection-background-color: #4fc3f7;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #4fc3f7; }
    QLineEdit:disabled { background-color: #252525; color: #666; }
    QPushButton { background-color: #0d7377; border: none; border-radius: 4px; padding: 8px 16px; color: white; font-weight: bold; }
    QPushButton:hover { background-color: #14919b; }
    QPushButton:pressed { background-color: #0a5c5f; }
    QPushButton:disabled { background-color: #333; color: #666; }
    QPushButton#danger { background-color: #c62828; }
    QPushButton#danger:hover { background-color: #e53935; }
    QPushButton#success { background-color: #2e7d32; }
    QPushButton#success:hover { background-color: #43a047; }
    QTableWidget { background-color: #252525; border: 1px solid #3c3c3c; gridline-color: #3c3c3c; selection-background-color: #0d7377; selection-color: white; }
    QTableWidget::item { padding: 6px; border-bottom: 1px solid #3c3c3c; }
    QTableWidget::item:selected { background-color: #0d7377; }
    QHeaderView::section { background-color: #2d2d2d; color: #4fc3f7; padding: 8px; border: none; border-right: 1px solid #3c3c3c; font-weight: bold; }
    QTabWidget::pane { border: 1px solid #3c3c3c; background-color: #1e1e1e; }
    QTabBar::tab { background-color: #2d2d2d; color: #aaa; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
    QTabBar::tab:selected { background-color: #0d7377; color: white; }
    QTabBar::tab:hover:!selected { background-color: #3c3c3c; color: #e0e0e0; }
    QMenuBar { background-color: #2d2d2d; color: #e0e0e0; }
    QMenuBar::item:selected { background-color: #0d7377; }
    QMenu { background-color: #2d2d2d; border: 1px solid #3c3c3c; }
    QMenu::item:selected { background-color: #0d7377; }
    QStatusBar { background-color: #2d2d2d; color: #aaa; }
    QScrollArea { border: none; }
    QLabel#title { font-size: 24px; font-weight: bold; color: #4fc3f7; }
    QLabel#subtitle { font-size: 14px; color: #aaa; }
    QLabel#clock { font-size: 28px; font-weight: bold; color: #4fc3f7; font-family: "Consolas", "Courier New", monospace; }
    QLabel#date { font-size: 16px; color: #aaa; }
    QLabel#info_label { color: #81c784; font-weight: bold; }
    QLabel#error_label { color: #e57373; font-weight: bold; }
    QLabel#webtime { font-size: 12px; font-family: "Consolas", "Courier New", monospace; }
    QComboBox::drop-down { border: none; width: 30px; }
    QComboBox QAbstractItemView { background-color: #2d2d2d; color: #e0e0e0; selection-background-color: #0d7377; }
    QDialog { background-color: #1e1e1e; }
    """

    LIGHT = """
    QMainWindow { background-color: #f5f5f5; }
    QWidget { background-color: #f5f5f5; color: #333333; }
    QGroupBox { border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #1565c0; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit, QPlainTextEdit {
        background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px; padding: 6px 10px; color: #333333; selection-background-color: #1976d2; selection-color: white;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #1976d2; }
    QLineEdit:disabled { background-color: #eeeeee; color: #999999; }
    QPushButton { background-color: #1976d2; border: none; border-radius: 4px; padding: 8px 16px; color: white; font-weight: bold; }
    QPushButton:hover { background-color: #1565c0; }
    QPushButton:pressed { background-color: #0d47a1; }
    QPushButton:disabled { background-color: #bdbdbd; color: #757575; }
    QPushButton#danger { background-color: #c62828; }
    QPushButton#danger:hover { background-color: #b71c1c; }
    QPushButton#success { background-color: #2e7d32; }
    QPushButton#success:hover { background-color: #1b5e20; }
    QTableWidget { background-color: #ffffff; border: 1px solid #cccccc; gridline-color: #e0e0e0; selection-background-color: #1976d2; selection-color: white; }
    QTableWidget::item { padding: 6px; border-bottom: 1px solid #e0e0e0; }
    QTableWidget::item:selected { background-color: #1976d2; }
    QHeaderView::section { background-color: #e3f2fd; color: #1565c0; padding: 8px; border: none; border-right: 1px solid #cccccc; font-weight: bold; }
    QTabWidget::pane { border: 1px solid #cccccc; background-color: #f5f5f5; }
    QTabBar::tab { background-color: #e0e0e0; color: #666666; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
    QTabBar::tab:selected { background-color: #1976d2; color: white; }
    QTabBar::tab:hover:!selected { background-color: #bdbdbd; color: #333333; }
    QMenuBar { background-color: #e3f2fd; color: #333333; }
    QMenuBar::item:selected { background-color: #1976d2; color: white; }
    QMenu { background-color: #ffffff; border: 1px solid #cccccc; }
    QMenu::item:selected { background-color: #1976d2; color: white; }
    QStatusBar { background-color: #e3f2fd; color: #666666; }
    QScrollArea { border: none; }
    QLabel#title { font-size: 24px; font-weight: bold; color: #1565c0; }
    QLabel#subtitle { font-size: 14px; color: #666666; }
    QLabel#clock { font-size: 28px; font-weight: bold; color: #1565c0; font-family: "Consolas", "Courier New", monospace; }
    QLabel#date { font-size: 16px; color: #666666; }
    QLabel#info_label { color: #2e7d32; font-weight: bold; }
    QLabel#error_label { color: #c62828; font-weight: bold; }
    QLabel#webtime { font-size: 12px; font-family: "Consolas", "Courier New", monospace; }
    QComboBox::drop-down { border: none; width: 30px; }
    QComboBox QAbstractItemView { background-color: #ffffff; color: #333333; selection-background-color: #1976d2; }
    QDialog { background-color: #f5f5f5; }
    """

    THEME_MAP = {
        'dark': DARK,
        'light': LIGHT,
    }


class WindowEffect:
    """Windows 窗口材质效果管理器"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if WindowEffect._initialized:
            return
        WindowEffect._initialized = True
        self._effect_impl = None
        self._is_win11 = False
        self._build = 0

        if HAS_FRAMELESS:
            try:
                self._effect_impl = _WindowEffect()
                ver = platform.version()
                parts = ver.split('.')
                if len(parts) >= 3:
                    self._build = int(parts[2])
                self._is_win11 = self._build >= 22000
            except Exception:
                self._effect_impl = None

    @classmethod
    def is_supported(cls) -> bool:
        if not HAS_FRAMELESS:
            return False
        inst = cls()
        return inst._effect_impl is not None

    @classmethod
    def is_win11(cls) -> bool:
        inst = cls()
        return inst._is_win11

    def apply_effect(self, hwnd: int, effect: str, dark_mode: bool = True):
        if not self._effect_impl:
            return
        effect = effect.lower().strip()
        hwnd = int(hwnd)
        if effect == 'none' or not effect:
            return
        try:
            if effect == 'acrylic':
                self._effect_impl.setAcrylicEffect(hwnd, dark_mode=dark_mode)
            elif effect == 'mica':
                self._effect_impl.setMicaEffect(hwnd, isAlt=False)
            elif effect == 'micaalt':
                self._effect_impl.setMicaEffect(hwnd, isAlt=True)
            elif effect == 'aero':
                self._effect_impl.setAeroEffect(hwnd)
        except Exception as e:
            print(f"[WindowEffect] 应用效果失败: {e}")


# ============================================
# 内嵌：添加/编辑/查看日志对话框
# ============================================

class LogDialog(QDialog):
    """添加/编辑/查看日志对话框"""
    log_saved = pyqtSignal()

    def __init__(self, mode="add", log_data=None, db=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.log_data = log_data or {}
        self.db = db
        self.setWindowTitle("添加日志" if mode == "add" else ("编辑日志" if mode == "edit" else "查看日志"))
        self.setMinimumWidth(750)
        self.setMinimumHeight(650)
        self.setup_ui()
        if log_data:
            self.load_data()
        if mode == "view":
            self.set_readonly()

    @staticmethod
    def _format_freq(freq_str):
        """格式化频率为保留3位小数的 MHz"""
        if not freq_str or not freq_str.strip():
            return ''
        digits = re.sub(r'[^0-9.]', '', freq_str.strip())
        if not digits:
            return ''
        try:
            return "{:.3f}MHz".format(float(digits))
        except ValueError:
            return freq_str.strip()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("日志记录")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 主内容区 - 左右分栏
        content = QHBoxLayout()
        content.setSpacing(20)

        # ===== 左栏 =====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)

        # -- 基本信息 --
        basic_group = QGroupBox("基本信息")
        basic_grid = QGridLayout()
        basic_grid.setSpacing(10)
        basic_grid.setColumnStretch(1, 1)

        self.txt_callsign = QLineEdit()
        self.txt_callsign.setPlaceholderText("呼号")
        # === 新增：呼号自动转大写 ===
        self.txt_callsign.textChanged.connect(self._auto_uppercase_callsign)
        basic_grid.addWidget(QLabel("对方呼号*:"), 0, 0)
        basic_grid.addWidget(self.txt_callsign, 0, 1)

        self.txt_freq = QLineEdit()
        self.txt_freq.setPlaceholderText("如：144.000MHz")
        basic_grid.addWidget(QLabel("频率:"), 1, 0)
        basic_grid.addWidget(self.txt_freq, 1, 1)

        # 时区显示（只读，自动从系统读取）
        self.lbl_timezone = QLabel(LogDialog._get_timezone_name())
        self.lbl_timezone.setStyleSheet("color: #81c784; font-weight: bold;")
        basic_grid.addWidget(QLabel("时区:"), 2, 0)
        basic_grid.addWidget(self.lbl_timezone, 2, 1)

        # 日期
        date_layout = QHBoxLayout()
        date_layout.setSpacing(5)

        self.spin_year = QSpinBox()
        self.spin_year.setRange(1900, 2100)
        self.spin_year.setValue(datetime.now().year)
        self.spin_month = QSpinBox()
        self.spin_month.setRange(1, 12)
        self.spin_month.setValue(datetime.now().month)
        self.spin_day = QSpinBox()
        self.spin_day.setRange(1, 31)
        self.spin_day.setValue(datetime.now().day)

        date_layout.addWidget(self.spin_year)
        date_layout.addWidget(QLabel("年"))
        date_layout.addWidget(self.spin_month)
        date_layout.addWidget(QLabel("月"))
        date_layout.addWidget(self.spin_day)
        date_layout.addWidget(QLabel("日"))
        date_layout.addStretch()

        basic_grid.addWidget(QLabel("日期*:"), 3, 0)
        basic_grid.addLayout(date_layout, 3, 1)

        # 时间
        time_layout = QHBoxLayout()
        time_layout.setSpacing(5)

        self.txt_time = QLineEdit()
        self.txt_time.setPlaceholderText("HHMM")
        self.txt_time.setMaximumWidth(80)

        time_layout.addWidget(self.txt_time)
        time_layout.addWidget(QLabel("(本地时间)"))
        time_layout.addStretch()

        basic_grid.addWidget(QLabel("时间*:"), 4, 0)
        basic_grid.addLayout(time_layout, 4, 1)

        # UTC 预览标签
        self.lbl_utc_preview = QLabel("UTC: --")
        self.lbl_utc_preview.setStyleSheet("color: #81c784; font-size: 11px;")
        basic_grid.addWidget(self.lbl_utc_preview, 5, 1)

        # 连接信号实时更新 UTC 预览（时区从系统读取，不需要监听）
        self.spin_year.valueChanged.connect(self.update_utc_preview)
        self.spin_month.valueChanged.connect(self.update_utc_preview)
        self.spin_day.valueChanged.connect(self.update_utc_preview)
        self.txt_time.textChanged.connect(self.update_utc_preview)

        self.cmb_mode = QComboBox()
        self.cmb_mode.setEditable(True)
        self.cmb_mode.addItems(["FM", "SSB", "CW", "AM", "FT8", "FT4", "JT65", "RTTY", "PSK31", "DIGITAL"])
        basic_grid.addWidget(QLabel("模式*:"), 6, 0)
        basic_grid.addWidget(self.cmb_mode, 6, 1)

        self.txt_qth = QLineEdit()
        self.txt_qth.setPlaceholderText("通联地点")
        basic_grid.addWidget(QLabel("QTH:"), 7, 0)
        basic_grid.addWidget(self.txt_qth, 7, 1)

        basic_group.setLayout(basic_grid)
        left_layout.addWidget(basic_group)

        # -- 信号报告 --
        rst_group = QGroupBox("信号报告")
        rst_layout = QGridLayout()
        rst_layout.setSpacing(10)

        self.txt_rst_self = QLineEdit()
        self.txt_rst_self.setPlaceholderText("如：59")
        self.txt_rst_self.setMaximumWidth(80)
        rst_layout.addWidget(QLabel("对方给我*:"), 0, 0)
        rst_layout.addWidget(self.txt_rst_self, 0, 1)
        rst_layout.addWidget(QLabel("(他听我)"), 0, 2)

        self.txt_rst_side = QLineEdit()
        self.txt_rst_side.setPlaceholderText("如：58")
        self.txt_rst_side.setMaximumWidth(80)
        rst_layout.addWidget(QLabel("我给对方*:"), 1, 0)
        rst_layout.addWidget(self.txt_rst_side, 1, 1)
        rst_layout.addWidget(QLabel("(我听他)"), 1, 2)

        rst_layout.setColumnStretch(3, 1)
        rst_group.setLayout(rst_layout)
        left_layout.addWidget(rst_group)

        left_layout.addStretch()
        content.addWidget(left_widget, stretch=1)

        # ===== 右栏 =====
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(15)

        # -- 功率与设备 --
        power_group = QGroupBox("功率与设备")
        power_layout = QGridLayout()
        power_layout.setSpacing(10)

        self.txt_power_self = QLineEdit("5W")
        self.txt_power_self.setPlaceholderText("5W")
        power_layout.addWidget(QLabel("我的功率*:"), 0, 0)
        power_layout.addWidget(self.txt_power_self, 0, 1)

        self.txt_power_side = QLineEdit()
        self.txt_power_side.setPlaceholderText("如：8W")
        power_layout.addWidget(QLabel("对方功率:"), 0, 2)
        power_layout.addWidget(self.txt_power_side, 0, 3)

        self.txt_device = QLineEdit("Device")
        self.txt_device.setPlaceholderText("Device")
        power_layout.addWidget(QLabel("设备:"), 1, 0)
        power_layout.addWidget(self.txt_device, 1, 1, 1, 3)

        power_group.setLayout(power_layout)
        right_layout.addWidget(power_group)

        # -- QSL 卡片 --
        qsl_group = QGroupBox("QSL 卡片")
        qsl_layout = QGridLayout()
        qsl_layout.setSpacing(10)

        self.txt_qsl_rx = QLineEdit()
        self.txt_qsl_rx.setPlaceholderText("YYYYMMDD (如...")
        qsl_layout.addWidget(QLabel("收到QSL:"), 0, 0)
        qsl_layout.addWidget(self.txt_qsl_rx, 0, 1)

        self.txt_qsl_send = QLineEdit()
        self.txt_qsl_send.setPlaceholderText("YYYYMMDD (如...")
        qsl_layout.addWidget(QLabel("发出QSL:"), 1, 0)
        qsl_layout.addWidget(self.txt_qsl_send, 1, 1)

        qsl_group.setLayout(qsl_layout)
        right_layout.addWidget(qsl_group)

        # -- 备注 --
        remark_group = QGroupBox("备注")
        remark_layout = QVBoxLayout()
        self.txt_remarks = QPlainTextEdit()
        self.txt_remarks.setPlaceholderText("其他备注信息...")
        self.txt_remarks.setMaximumHeight(120)
        remark_layout.addWidget(self.txt_remarks)
        remark_group.setLayout(remark_layout)
        right_layout.addWidget(remark_group)

        right_layout.addStretch()
        content.addWidget(right_widget, stretch=1)

        layout.addLayout(content)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if self.mode != "view":
            self.btn_save = QPushButton("保存")
            self.btn_save.setObjectName("success")
            self.btn_save.setMinimumWidth(120)
            self.btn_save.clicked.connect(self.save_log)
            btn_layout.addWidget(self.btn_save)

        self.btn_close = QPushButton("关闭")
        self.btn_close.setMinimumWidth(120)
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def load_data(self):
        d = self.log_data
        self.txt_callsign.setText(str(d.get('Callsign', '')))
        self.txt_freq.setText(str(d.get('Freq', '')))
        try:
            self.spin_year.setValue(int(d.get('Year', datetime.now().year)))
            self.spin_month.setValue(int(d.get('Month', datetime.now().month)))
            self.spin_day.setValue(int(d.get('Day', datetime.now().day)))
        except:
            pass
        self.txt_timezone.setText(str(d.get('Timezone', 'UTC')))
        self.txt_time.setText(str(d.get('Time', '')))
        self.cmb_mode.setCurrentText(str(d.get('Mode', 'FM')))
        self.txt_qth.setText(str(d.get('QTH', '')))
        self.txt_rst_self.setText(str(d.get('Rst_self', '')))
        self.txt_rst_side.setText(str(d.get('Rst_side', '')))
        self.txt_power_self.setText(str(d.get('Power_self', '5W')))
        self.txt_power_side.setText(str(d.get('Power_side', '')))
        self.txt_device.setText(str(d.get('Device', 'Device')))
        self.txt_qsl_rx.setText(str(d.get('QSL_RX', '')))
        self.txt_qsl_send.setText(str(d.get('QSL_SEND', '')))
        self.txt_remarks.setPlainText(str(d.get('Remarks', '')))

    def set_readonly(self):
        for w in [self.txt_callsign, self.txt_freq, self.spin_year, self.spin_month,
                  self.spin_day, self.txt_time, self.cmb_mode,
                  self.txt_qth, self.txt_rst_self, self.txt_rst_side, self.txt_power_self,
                  self.txt_power_side, self.txt_device, self.txt_qsl_rx, self.txt_qsl_send,
                  self.txt_remarks]:
            w.setEnabled(False)

    @staticmethod
    def _get_system_timezone():
        """获取系统本地时区"""
        from datetime import timezone, timedelta
        # 通过当前时间的偏移量计算
        now = datetime.now()
        utc_now = datetime.utcnow()
        offset = now - utc_now
        # 四舍五入到整小时（处理夏令时等）
        offset_hours = round(offset.total_seconds() / 3600)
        return timezone(timedelta(hours=offset_hours))

    @staticmethod
    def _get_timezone_name():
        """获取系统时区名称"""
        try:
            import time
            return time.tzname[0] if time.tzname else "LOCAL"
        except:
            return "LOCAL"

    def update_utc_preview(self):
        """实时计算并显示 UTC 时间预览"""
        try:
            year = self.spin_year.value()
            month = self.spin_month.value()
            day = self.spin_day.value()
            time_str = self.txt_time.text().strip()

            if not time_str or len(time_str) < 4:
                self.lbl_utc_preview.setText("UTC: --")
                return

            # 解析时间
            time_digits = ''.join(c for c in time_str if c.isdigit())
            if len(time_digits) >= 4:
                hour = int(time_digits[:2])
                minute = int(time_digits[2:4])
                second = int(time_digits[4:6]) if len(time_digits) >= 6 else 0
            else:
                return

            from datetime import timezone

            # 构建本地时间（使用系统时区）
            local_dt = datetime(year, month, day, hour, minute, second)
            tz = LogDialog._get_system_timezone()

            local_dt = local_dt.replace(tzinfo=tz)
            utc_dt = local_dt.astimezone(timezone.utc)

            # 检查是否跨天
            day_changed = (utc_dt.year != year or utc_dt.month != month or utc_dt.day != day)
            cross_hint = " (跨天!)" if day_changed else ""

            self.lbl_utc_preview.setText(
                "UTC: {}-{:02d}-{:02d} {}{}".format(
                    utc_dt.year, utc_dt.month, utc_dt.day,
                    utc_dt.strftime('%H:%M'), cross_hint
                )
            )
            if day_changed:
                self.lbl_utc_preview.setStyleSheet("color: #ffb74d; font-size: 11px; font-weight: bold;")
            else:
                self.lbl_utc_preview.setStyleSheet("color: #81c784; font-size: 11px;")

        except Exception:
            self.lbl_utc_preview.setText("UTC: --")

    def _auto_uppercase_callsign(self, text: str):
        """呼号输入自动转大写"""
        cursor_pos = self.txt_callsign.cursorPosition()
        upper_text = text.upper()
        if text != upper_text:
            self.txt_callsign.blockSignals(True)
            self.txt_callsign.setText(upper_text)
            self.txt_callsign.setCursorPosition(cursor_pos)
            self.txt_callsign.blockSignals(False)

    def save_log(self):
        # 校验必填项
        callsign = self.txt_callsign.text().strip().upper()
        if not callsign:
            QMessageBox.warning(self, "提示", "对方呼号不能为空")
            return

        time_str = self.txt_time.text().strip()
        if not time_str:
            QMessageBox.warning(self, "提示", "时间不能为空")
            return

        # 时区转换：将系统本地时间转换为 UTC
        year = self.spin_year.value()
        month = self.spin_month.value()
        day = self.spin_day.value()

        # 解析时间字符串为 HHMM 或 HHMMSS
        time_digits = ''.join(c for c in time_str if c.isdigit())
        if len(time_digits) >= 4:
            hour = int(time_digits[:2])
            minute = int(time_digits[2:4])
            second = int(time_digits[4:6]) if len(time_digits) >= 6 else 0
        else:
            hour, minute, second = 0, 0, 0

        try:
            from datetime import timezone

            # 使用系统本地时区转换为 UTC
            local_dt = datetime(year, month, day, hour, minute, second)
            tz = LogDialog._get_system_timezone()

            local_dt = local_dt.replace(tzinfo=tz)
            utc_dt = local_dt.astimezone(timezone.utc)

            year = utc_dt.year
            month = utc_dt.month
            day = utc_dt.day
            time_str = utc_dt.strftime("%H%M")

        except Exception as e:
            print("[HamLog] 时区转换失败: {}".format(e))

        rst_self = self.txt_rst_self.text().strip()
        rst_side = self.txt_rst_side.text().strip()
        if not rst_self or not rst_side:
            QMessageBox.warning(self, "提示", "信号报告不能为空")
            return

        power_self = self.txt_power_self.text().strip()
        if not power_self:
            QMessageBox.warning(self, "提示", "我的功率不能为空")
            return

        log_dict = {
            'Callsign': callsign,
            'Freq': self._format_freq(self.txt_freq.text().strip()),
            'Year': year,
            'Month': month,
            'Day': day,
            'Time': time_str,
            'Mode': self.cmb_mode.currentText().strip().upper(),
            'Power_self': power_self,
            'Power_side': self.txt_power_side.text().strip(),
            'Rst_self': rst_self,
            'Rst_side': rst_side,
            'QTH': self.txt_qth.text().strip(),
            'Device': self.txt_device.text().strip(),
            'QSL_RX': self.txt_qsl_rx.text().strip(),
            'QSL_SEND': self.txt_qsl_send.text().strip(),
            'Remarks': self.txt_remarks.toPlainText().strip(),
        }

        if self.mode == "edit" and self.log_data:
            log_id = self.log_data.get('id')
            ok, msg = self.db.update(log_id, log_dict)
        else:
            ok, msg = self.db.add(log_dict)

        if ok:
            from app_logger import get_logger
            logger = get_logger()
            mode_str = "编辑" if self.mode == "edit" else "添加"
            logger.info("LogDialog", f"{mode_str}日志成功: {callsign}")
            QMessageBox.information(self, "成功", msg)
            self.log_saved.emit()
            self.accept()
        else:
            from app_logger import get_logger
            logger = get_logger()
            logger.error("LogDialog", f"保存日志失败: {msg}")
            QMessageBox.warning(self, "失败", msg)


# ============================================
# 内嵌：软件设置对话框
# ============================================

class SettingsDialog(QDialog):
    """软件设置对话框"""
    settings_changed = pyqtSignal()
    theme_changed = pyqtSignal(str)
    intertime_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("软件设置")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)
        self.settings = SettingsManager()
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("软件设置")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 主内容 - 左右分栏
        content = QHBoxLayout()
        content.setSpacing(20)

        # ===== 左栏 =====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)

        # -- 本台信息 --
        station_group = QGroupBox("本台信息")
        station_grid = QGridLayout()
        station_grid.setSpacing(10)
        station_grid.setColumnStretch(1, 1)

        self.txt_my_callsign = QLineEdit()
        self.txt_my_callsign.setPlaceholderText("Your Callsign")
        station_grid.addWidget(QLabel("本台呼号:"), 0, 0)
        station_grid.addWidget(self.txt_my_callsign, 0, 1)

        self.txt_my_name = QLineEdit()
        self.txt_my_name.setPlaceholderText("操作员姓名")
        station_grid.addWidget(QLabel("操作员:"), 1, 0)
        station_grid.addWidget(self.txt_my_name, 1, 1)

        self.txt_my_qth = QLineEdit()
        self.txt_my_qth.setPlaceholderText("常用QTH")
        station_grid.addWidget(QLabel("常用QTH:"), 2, 0)
        station_grid.addWidget(self.txt_my_qth, 2, 1)

        self.txt_my_grid = QLineEdit()
        self.txt_my_grid.setPlaceholderText("网格定位（如：OM66）")
        station_grid.addWidget(QLabel("网格定位:"), 3, 0)
        station_grid.addWidget(self.txt_my_grid, 3, 1)

        station_group.setLayout(station_grid)
        left_layout.addWidget(station_group)

        # -- 默认参数 --
        default_group = QGroupBox("默认参数")
        default_grid = QGridLayout()
        default_grid.setSpacing(10)
        default_grid.setColumnStretch(1, 1)

        self.cmb_default_mode = QComboBox()
        self.cmb_default_mode.setEditable(True)
        self.cmb_default_mode.addItems(["FM", "SSB", "CW", "AM", "FT8", "FT4", "JT65", "RTTY", "PSK31"])
        default_grid.addWidget(QLabel("默认模式:"), 0, 0)
        default_grid.addWidget(self.cmb_default_mode, 0, 1)

        self.txt_default_power = QLineEdit("5W")
        default_grid.addWidget(QLabel("默认功率:"), 1, 0)
        default_grid.addWidget(self.txt_default_power, 1, 1)

        self.txt_default_device = QLineEdit("Device")
        default_grid.addWidget(QLabel("默认设备:"), 2, 0)
        default_grid.addWidget(self.txt_default_device, 2, 1)

        default_group.setLayout(default_grid)
        left_layout.addWidget(default_group)

        left_layout.addStretch()
        content.addWidget(left_widget, stretch=1)

        # ===== 右栏 =====
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(15)

        # -- 外观 --
        theme_group = QGroupBox("外观")
        theme_layout = QFormLayout()
        theme_layout.setSpacing(10)

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem("深色", "dark")
        self.cmb_theme.addItem("浅色", "light")
        theme_layout.addRow("主题:", self.cmb_theme)

        theme_group.setLayout(theme_layout)
        right_layout.addWidget(theme_group)

        # -- 网络延迟检测 --
        intertime_group = QGroupBox("网络延迟检测")
        intertime_layout = QVBoxLayout()
        intertime_layout.setSpacing(10)

        self.chk_intertime = QCheckBox("启用实时网络延迟检测")
        intertime_layout.addWidget(self.chk_intertime)

        intertime_layout.addWidget(QLabel("检测节点 (最多5个):"))
        self.lst_nodes = QListWidget()
        self.lst_nodes.setMaximumHeight(120)
        intertime_layout.addWidget(self.lst_nodes)

        node_btn_layout = QHBoxLayout()
        self.btn_add_node = QPushButton("+ 添加")
        self.btn_add_node.clicked.connect(self.add_node)
        self.btn_del_node = QPushButton("- 删除")
        self.btn_del_node.clicked.connect(self.del_node)
        self.btn_clear_nodes = QPushButton("清空")
        self.btn_clear_nodes.clicked.connect(self.clear_nodes)
        node_btn_layout.addWidget(self.btn_add_node)
        node_btn_layout.addWidget(self.btn_del_node)
        node_btn_layout.addWidget(self.btn_clear_nodes)
        node_btn_layout.addStretch()
        intertime_layout.addLayout(node_btn_layout)

        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("超时时间:"))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 30)
        self.spin_timeout.setSuffix(" 秒")
        timeout_layout.addWidget(self.spin_timeout)
        timeout_layout.addStretch()
        intertime_layout.addLayout(timeout_layout)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("刷新间隔:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 300)
        self.spin_interval.setSuffix(" 秒")
        interval_layout.addWidget(self.spin_interval)
        interval_layout.addStretch()
        intertime_layout.addLayout(interval_layout)

        hint = QLabel("提示: 节点过多或间隔过短可能影响性能")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        intertime_layout.addWidget(hint)

        intertime_group.setLayout(intertime_layout)
        right_layout.addWidget(intertime_group)

        right_layout.addStretch()
        content.addWidget(right_widget, stretch=1)

        layout.addLayout(content)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("success")
        self.btn_save.setMinimumWidth(100)
        self.btn_save.clicked.connect(self.save_settings)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def load_settings(self):
        self.txt_my_callsign.setText(self.settings.get('my_callsign', 'Your Callsign'))
        self.txt_my_name.setText(self.settings.get('my_name', ''))
        self.txt_my_qth.setText(self.settings.get('my_qth', ''))
        self.txt_my_grid.setText(self.settings.get('my_grid', ''))

        self.cmb_default_mode.setCurrentText(self.settings.get('default_mode', 'FM'))
        self.txt_default_power.setText(self.settings.get('default_power', '5W'))
        self.txt_default_device.setText(self.settings.get('default_device', 'Device'))

        theme = self.settings.get('theme', 'dark')
        idx = self.cmb_theme.findData(theme)
        if idx >= 0:
            self.cmb_theme.setCurrentIndex(idx)

        self.chk_intertime.setChecked(self.settings.get('intertime_enabled', '1') == '1')
        raw_nodes = self.settings.get('intertime_nodes', 'www.baidu.com')
        for node in raw_nodes.split(','):
            node = node.strip()
            if node:
                self.lst_nodes.addItem(node)

        self.spin_timeout.setValue(int(self.settings.get('intertime_timeout', '2') or '2'))
        self.spin_interval.setValue(int(self.settings.get('intertime_interval', '5') or '5'))

    def add_node(self):
        if self.lst_nodes.count() >= 5:
            QMessageBox.warning(self, "提示", "最多只能添加5个检测节点")
            return
        text, ok = QInputDialog.getText(self, "添加节点", "输入节点地址（如 www.baidu.com）:")
        if ok and text.strip():
            self.lst_nodes.addItem(text.strip())

    def del_node(self):
        row = self.lst_nodes.currentRow()
        if row >= 0:
            self.lst_nodes.takeItem(row)

    def clear_nodes(self):
        self.lst_nodes.clear()

    def save_settings(self):
        self.settings.set('my_callsign', self.txt_my_callsign.text().strip())
        self.settings.set('my_name', self.txt_my_name.text().strip())
        self.settings.set('my_qth', self.txt_my_qth.text().strip())
        self.settings.set('my_grid', self.txt_my_grid.text().strip())

        self.settings.set('default_mode', self.cmb_default_mode.currentText().strip())
        self.settings.set('default_power', self.txt_default_power.text().strip())
        self.settings.set('default_device', self.txt_default_device.text().strip())

        new_theme = self.cmb_theme.currentData()
        old_theme = self.settings.get('theme', 'dark')
        self.settings.set('theme', new_theme)

        self.settings.set('intertime_enabled', '1' if self.chk_intertime.isChecked() else '0')
        nodes = [self.lst_nodes.item(i).text() for i in range(self.lst_nodes.count())]
        self.settings.set('intertime_nodes', ','.join(nodes))
        self.settings.set('intertime_timeout', str(self.spin_timeout.value()))
        self.settings.set('intertime_interval', str(self.spin_interval.value()))

        self.settings_changed.emit()
        if new_theme != old_theme:
            self.theme_changed.emit(new_theme)
        self.intertime_settings_changed.emit()

        QMessageBox.information(self, "保存成功", "设置已保存")
        self.accept()


# ============================================
# 网络时延检测工作线程
# ============================================

class IntertimeWorker(QThread):
    """网络时延检测工作线程"""
    result_ready = pyqtSignal(list)  # [(node, ok, val), ...]

    def __init__(self, nodes, timeout, parent=None):
        super().__init__(parent)
        self.nodes = nodes
        self.timeout = timeout
        self._running = True

    def run(self):
        results = []
        for node in self.nodes:
            if not self._running:
                break
            try:
                ok, val = get_ping_time(node, timeout=self.timeout)
                try:
                    numeric_val = float(val) if val != "<1" else 0.5
                except (ValueError, TypeError):
                    numeric_val = None
                results.append((node, ok, numeric_val if ok else None))
            except Exception:
                results.append((node, False, None))
        if self._running:
            self.result_ready.emit(results)

    def stop(self):
        self._running = False
        self.wait(1000)

    def isRunning(self):
        return super().isRunning()


# ============================================
# 主窗口
# ============================================

class MainWindow(FramelessWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.settings = SettingsManager()
        self.current_theme = self.settings.get('theme', 'dark')
        self.window_effect = self.settings.get('window_effect', 'none')
        self.intertime_timer = None
        self.intertime_nodes = []
        self.intertime_enabled = False
        self.intertime_interval = 5
        self.intertime_timeout = 2
        self.intertime_worker = None

        # === 新增：初始化日志系统 ===
        self.logger = get_logger()
        self.logger.info("MainWindow", "主窗口初始化开始")

        # === 新增：初始化代理管理器 ===
        self.proxy_mgr = get_proxy_manager()
        self.proxy_mgr.load_from_settings(self.settings)

        # === 新增：初始化字体设置 ===
        self._init_font_settings()

        self.init_ui()
        self.load_logs()
        self.start_clock()
        self.init_intertime()
        self.apply_theme()
        self.update_manager = UpdateManager(self, CURRENT_VERSION)
        QTimer.singleShot(3000, lambda: auto_check_on_startup(self, CURRENT_VERSION))

        self.logger.info("MainWindow", "主窗口初始化完成")

    def _init_font_settings(self):
        """初始化字体设置"""
        font_config = load_font_settings(self.settings)
        app = QApplication.instance()
        if app:
            FontManager.apply_global_font(app, font_config['global_font'], font_config['global_size'])

        # 递归更新主窗口及其所有子控件的字体
        # QApplication.setFont() 只影响后续创建的控件，已存在的控件需要手动刷新
        global_font = QFont(font_config['global_font'], font_config['global_size'])

        def _update_fonts(widget):
            widget.setFont(global_font)
            for child in widget.findChildren(QWidget):
                child.setFont(global_font)

        _update_fonts(self)

        # 刷新表格字体（使用单独配置的表格字体）
        if hasattr(self, 'log_table') and self.log_table is not None:
            self._refresh_table_font()

    def _refresh_table_font(self):
        """刷新表格字体和行高"""
        font_config = load_font_settings(self.settings)
        table_font_name = font_config['table_font']
        table_font_size = font_config['table_size']
        row_height = font_config['row_height']

        font = QFont(table_font_name, table_font_size)
        self.log_table.setFont(font)

        # 刷新所有行的行高
        for row in range(self.log_table.rowCount()):
            self.log_table.setRowHeight(row, row_height)

    def init_ui(self):
        self.setWindowTitle("HamLog - 业余无线电台日志管理系统")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        menubar = None
        try:
            menubar = self.menuBar()
        except AttributeError:
            menubar = QMenuBar(self)
            try:
                self.setMenuBar(menubar)
            except AttributeError:
                pass

        if menubar:
            file_menu = menubar.addMenu("文件")
            action_export_adif = QAction("导出 为ADIF文件", self)
            action_export_adif.setShortcut("Ctrl+E")
            action_export_adif.triggered.connect(self.open_export_dialog)
            file_menu.addAction(action_export_adif)
            file_menu.addSeparator()
            exit_action = QAction("退出", self)
            exit_action.setShortcut(QKeySequence("Ctrl+Q"))
            exit_action.triggered.connect(self.close)
            file_menu.addAction(exit_action)

            log_menu = menubar.addMenu("日志")
            add_action = QAction("添加日志", self)
            add_action.setShortcut(QKeySequence("Ctrl+N"))
            add_action.triggered.connect(self.open_add_dialog)
            log_menu.addAction(add_action)

            tools_menu = menubar.addMenu("工具")
            action_qrz_lookup = QAction("QRZ.com 呼号查询", self)
            action_qrz_lookup.setShortcut("Ctrl+Q")
            action_qrz_lookup.triggered.connect(self.open_qrz_lookup_dialog)
            tools_menu.addAction(action_qrz_lookup)
            tools_menu.addSeparator()
            action_upload_lotw = QAction("上传到 LoTW...", self)
            action_upload_lotw.setShortcut("Ctrl+L")
            action_upload_lotw.triggered.connect(self.open_upload_dialog)
            tools_menu.addAction(action_upload_lotw)

            settings_menu = menubar.addMenu("设置")
            settings_action = QAction("软件设置", self)
            settings_action.setShortcut(QKeySequence("Ctrl+,"))
            settings_action.triggered.connect(self.open_settings)
            settings_menu.addAction(settings_action)

            # === 新增：字体设置 ===
            font_action = QAction("字体与界面...", self)
            font_action.triggered.connect(self.open_font_settings)
            settings_menu.addAction(font_action)

            # === 新增：代理设置 ===
            proxy_action = QAction("代理设置...", self)
            proxy_action.triggered.connect(self.open_proxy_settings)
            settings_menu.addAction(proxy_action)

            settings_menu.addSeparator()

            # === 新增：运行日志 ===
            log_action = QAction("查看运行日志", self)
            log_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
            log_action.triggered.connect(self.open_log_viewer)
            settings_menu.addAction(log_action)

            help_menu = menubar.addMenu("帮助")
            about_action = QAction("关于", self)
            about_action.triggered.connect(self.show_about)
            help_menu.addAction(about_action)
            help_menu.addSeparator()

            # 作者主页
            author_action = QAction("作者主页", self)
            author_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/1297822096")))
            help_menu.addAction(author_action)

            # GitHub
            github_action = QAction("GitHub", self)
            github_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/ARPRC-BA8AQA/HamLog")))
            help_menu.addAction(github_action)

            help_menu.addSeparator()

            # 清空数据库
            clear_db_action = QAction("清空数据库", self)
            clear_db_action.triggered.connect(self.clear_database)
            help_menu.addAction(clear_db_action)

            help_menu.addSeparator()
            check_update_action = QAction("检查更新", self)
            check_update_action.triggered.connect(self.check_update_manual)
            help_menu.addAction(check_update_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setSpacing(20)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(5)

        self.callsign_label = QLabel("Your Callsign")
        self.callsign_label.setObjectName("title")
        self.callsign_label.setStyleSheet("font-size: 32px;")
        info_layout.addWidget(self.callsign_label)

        self.info_detail = QLabel("操作员：-  |  QTH：-  |  网格：-")
        self.info_detail.setObjectName("subtitle")
        info_layout.addWidget(self.info_detail)

        top_layout.addWidget(info_widget, stretch=1)

        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setSpacing(30)

        self.total_label = QLabel("总通联：0")
        self.total_label.setStyleSheet("font-size: 16px; color: #81c784;")
        stats_layout.addWidget(self.total_label)

        self.today_label = QLabel("今日：0")
        self.today_label.setStyleSheet("font-size: 16px; color: #ffb74d;")
        stats_layout.addWidget(self.today_label)

        top_layout.addWidget(stats_widget)

        clock_widget = QWidget()
        clock_layout = QVBoxLayout(clock_widget)
        clock_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_layout.setSpacing(4)
        clock_layout.setContentsMargins(0, 0, 0, 0)

        self.clock_label = QLabel("00:00:00")
        self.clock_label.setObjectName("clock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_layout.addWidget(self.clock_label)

        self.date_label = QLabel("2026年06月15日 星期一")
        self.date_label.setObjectName("date")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_layout.addWidget(self.date_label)

        intertime_widget = QWidget()
        intertime_layout = QHBoxLayout(intertime_widget)
        intertime_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        intertime_layout.setSpacing(8)
        intertime_layout.setContentsMargins(0, 6, 0, 0)

        self.intertime_icon = QLabel("●")
        self.intertime_icon.setStyleSheet("color: #666; font-size: 10px;")
        intertime_layout.addWidget(self.intertime_icon)

        self.intertime_label = QLabel("已关闭")
        self.intertime_label.setObjectName("webtime")
        self.intertime_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        intertime_layout.addWidget(self.intertime_label)

        clock_layout.addWidget(intertime_widget)

        top_layout.addWidget(clock_widget)

        main_layout.addWidget(top_widget)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3c3c3c;")
        main_layout.addWidget(line)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索呼号、QTH、设备、备注...")
        self.search_edit.setFixedWidth(300)
        self.search_edit.returnPressed.connect(self.search_logs)
        toolbar.addWidget(self.search_edit)

        search_btn = QPushButton("搜索")
        search_btn.setFixedWidth(80)
        search_btn.clicked.connect(self.search_logs)
        toolbar.addWidget(search_btn)

        toolbar.addStretch()

        qrz_btn = QPushButton("QRZ查询")
        qrz_btn.setObjectName("success")
        qrz_btn.setFixedWidth(120)
        qrz_btn.setToolTip("在QRZ.com查询呼号信息 (Ctrl+Q)")
        qrz_btn.clicked.connect(self.open_qrz_lookup_dialog)
        toolbar.addWidget(qrz_btn)

        add_btn = QPushButton("+ 添加日志")
        add_btn.setObjectName("success")
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self.open_add_dialog)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.load_logs)
        toolbar.addWidget(refresh_btn)

        main_layout.addLayout(toolbar)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(17)
        self.log_table.setHorizontalHeaderLabels([
            "ID", "呼号", "频率", "年", "月", "日", "时间", "模式",
            "我的功率", "对方功率", "给我报告", "我给报告", "QTH", "设备",
            "收到QSL", "发出QSL", "备注"
        ])
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.log_table.setColumnHidden(0, True)

        # UTC 时间提示 - 放在表格上方醒目位置
        self.utc_hint_label = QLabel("⏰ 以下日志时间均为 UTC 时间")
        self.utc_hint_label.setStyleSheet(
            "color: #ffb74d; font-size: 12px; font-weight: bold; "
            "padding: 4px 10px; background-color: #2d2d2d; "
            "border: 1px solid #3c3c3c; border-radius: 4px;"
        )
        main_layout.addWidget(self.utc_hint_label)

        self.log_table.doubleClicked.connect(self.on_table_double_click)
        self.log_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self.show_context_menu)

        main_layout.addWidget(self.log_table)

        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")

        self.load_station_info()
        self.apply_window_effect()

    def apply_window_effect(self):
        effect = self.settings.get('window_effect', 'none')
        if effect != 'none' and WindowEffect.is_supported():
            hwnd = int(self.winId())
            is_dark = self.current_theme in ('dark', 'cyberpunk', 'forest', 'sunset', 'ocean', 'midnight')
            inst = WindowEffect()
            inst.apply_effect(hwnd, effect, dark_mode=is_dark)

    def apply_theme(self):
        sheet = StyleSheet.THEME_MAP.get(self.current_theme, StyleSheet.DARK)
        self.setStyleSheet(sheet)
        # 同步更新 UTC 提示样式
        if hasattr(self, 'utc_hint_label'):
            if self.current_theme == 'light':
                self.utc_hint_label.setStyleSheet(
                    "color: #e65100; font-size: 12px; font-weight: bold; "
                    "padding: 4px 10px; background-color: #fff3e0; "
                    "border: 1px solid #ffcc80; border-radius: 4px;"
                )
            else:
                self.utc_hint_label.setStyleSheet(
                    "color: #ffb74d; font-size: 12px; font-weight: bold; "
                    "padding: 4px 10px; background-color: #2d2d2d; "
                    "border: 1px solid #3c3c3c; border-radius: 4px;"
                )

    def start_clock(self):
        self.update_clock()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

    def update_clock(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S"))
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        self.date_label.setText(f"{now.year}年{now.month:02d}月{now.day:02d}日 {weekdays[now.weekday()]}")

    def load_station_info(self):
        callsign = self.settings.get('my_callsign', 'Your Callsign')
        name = self.settings.get('my_name', '')
        qth = self.settings.get('my_qth', '')
        grid = self.settings.get('my_grid', '')

        self.callsign_label.setText(callsign)
        detail = []
        if name:
            detail.append("操作员：" + name)
        if qth:
            detail.append("QTH：" + qth)
        if grid:
            detail.append("网格：" + grid)

        if detail:
            self.info_detail.setText("  |  ".join(detail))
        else:
            self.info_detail.setText("点击设置配置本台信息")

    def load_logs(self):
        logs = self.db.get_all()
        self.populate_table(logs)
        self.update_stats(logs)
        self.statusbar.showMessage("共 " + str(len(logs)) + " 条记录")
        self.logger.debug("MainWindow", f"加载了 {len(logs)} 条日志记录")

    def populate_table(self, logs):
        self.log_table.setRowCount(len(logs))
        row_height = max(22, min(60, int(self.settings.get('table_row_height', '28') or '28')))
        font_size = max(8, min(20, int(self.settings.get('table_font_size', '10') or '10')))
        show_id = self.settings.get('show_id_column', '0') == '1'

        # === 新增：读取表格字体设置 ===
        table_font_name = self.settings.get('table_font', 'Microsoft YaHei')

        self.log_table.setColumnHidden(0, not show_id)
        font = QFont(table_font_name, font_size)
        self.log_table.setFont(font)

        for row, log in enumerate(logs):
            self.log_table.setItem(row, 0, QTableWidgetItem(str(log.get('id', ''))))
            self.log_table.setItem(row, 1, QTableWidgetItem(str(log.get('Callsign', ''))))
            self.log_table.setItem(row, 2, QTableWidgetItem(str(log.get('Freq', ''))))
            self.log_table.setItem(row, 3, QTableWidgetItem(str(log.get('Year', ''))))
            self.log_table.setItem(row, 4, QTableWidgetItem(str(log.get('Month', ''))))
            self.log_table.setItem(row, 5, QTableWidgetItem(str(log.get('Day', ''))))
            self.log_table.setItem(row, 6, QTableWidgetItem(str(log.get('Time', ''))))
            self.log_table.setItem(row, 7, QTableWidgetItem(str(log.get('Mode', ''))))
            self.log_table.setItem(row, 8, QTableWidgetItem(str(log.get('Power_self', ''))))
            self.log_table.setItem(row, 9, QTableWidgetItem(str(log.get('Power_side', ''))))
            self.log_table.setItem(row, 10, QTableWidgetItem(str(log.get('Rst_self', ''))))
            self.log_table.setItem(row, 11, QTableWidgetItem(str(log.get('Rst_side', ''))))
            self.log_table.setItem(row, 12, QTableWidgetItem(str(log.get('QTH', ''))))
            self.log_table.setItem(row, 13, QTableWidgetItem(str(log.get('Device', ''))))
            self.log_table.setItem(row, 14, QTableWidgetItem(str(log.get('QSL_RX', ''))))
            self.log_table.setItem(row, 15, QTableWidgetItem(str(log.get('QSL_SEND', ''))))
            self.log_table.setItem(row, 16, QTableWidgetItem(str(log.get('Remarks', ''))))
            self.log_table.setRowHeight(row, row_height)

    def update_stats(self, logs=None):
        if logs is None:
            logs = self.db.get_all()
        total = len(logs)
        today = datetime.now().strftime("%Y%m%d")
        today_count = 0
        for log in logs:
            y = str(log.get('Year', ''))
            m = str(log.get('Month', '')).zfill(2)
            d = str(log.get('Day', '')).zfill(2)
            if y + m + d == today:
                today_count += 1

        self.total_label.setText("总通联：" + str(total))
        self.today_label.setText("今日：" + str(today_count))

    def search_logs(self):
        keyword = self.search_edit.text().strip()
        if not keyword:
            self.load_logs()
            return

        logs = self.db.search(keyword)
        self.populate_table(logs)
        self.statusbar.showMessage('搜索 "' + keyword + '" 找到 ' + str(len(logs)) + ' 条记录')

    def open_add_dialog(self):
        dialog = LogDialog(mode="add", db=self.db, parent=self)
        dialog.log_saved.connect(self.load_logs)
        dialog.exec()

    def open_edit_dialog(self, log_id):
        log_data = self.db.get_by_id(log_id)
        if log_data:
            dialog = LogDialog(mode="edit", log_data=log_data, db=self.db, parent=self)
            dialog.log_saved.connect(self.load_logs)
            dialog.exec()

    def open_view_dialog(self, log_id):
        log_data = self.db.get_by_id(log_id)
        if log_data:
            dialog = LogDialog(mode="view", log_data=log_data, db=self.db, parent=self)
            dialog.exec()

    def open_export_dialog(self):
        db_path = self.db.db_path
        dialog = ADIFExportDialog(db_path=db_path, parent=self)
        dialog.exec()

    def open_upload_dialog(self):
        dialog = LoTWUploadDialog(parent=self)
        dialog.exec()

    def open_qrz_lookup_dialog(self):
        preset_callsign = self.search_edit.text().strip().upper()
        dialog = QRZLookupDialog(callsign=preset_callsign, parent=self)
        dialog.apply_info.connect(self.on_qrz_info_applied)
        dialog.exec()

    def on_qrz_info_applied(self, info: dict):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = f"呼号: {info.get('callsign', '')}\n"
        text += f"国家: {info.get('country', '')}\n"
        text += f"QTH: {info.get('qth', '')}\n"
        text += f"网格: {info.get('grid', '')}\n"
        text += f"QRZ: {info.get('url', '')}"
        clipboard.setText(text)
        self.statusbar.showMessage(f"QRZ信息已复制到剪贴板: {info.get('callsign', '')}", 5000)

    def on_table_double_click(self, index):
        row = index.row()
        if row < 0:
            return
        item = self.log_table.item(row, 0)
        if item is None:
            return
        try:
            log_id = int(item.text())
        except ValueError:
            return
        self.open_edit_dialog(log_id)

    def show_context_menu(self, position):
        row = self.log_table.rowAt(position.y())
        if row < 0:
            return

        item = self.log_table.item(row, 0)
        if item is None:
            return
        try:
            log_id = int(item.text())
        except ValueError:
            return

        callsign = self.log_table.item(row, 1).text() if self.log_table.item(row, 1) else ""

        menu = QMenu(self)

        view_action = QAction("查看 " + callsign, self)
        view_action.triggered.connect(lambda: self.open_view_dialog(log_id))
        menu.addAction(view_action)

        edit_action = QAction("编辑 " + callsign, self)
        edit_action.triggered.connect(lambda: self.open_edit_dialog(log_id))
        menu.addAction(edit_action)

        menu.addSeparator()

        qrz_action = QAction("QRZ查询 " + callsign, self)
        qrz_action.triggered.connect(lambda: self.open_qrz_lookup_for_callsign(callsign))
        menu.addAction(qrz_action)

        menu.addSeparator()

        delete_action = QAction("删除 " + callsign, self)
        delete_action.triggered.connect(lambda: self.delete_log(log_id, callsign))
        menu.addAction(delete_action)

        menu.exec(self.log_table.viewport().mapToGlobal(position))

    def delete_log(self, log_id, callsign):
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除与 " + callsign + " 的通联记录吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self.db.delete(log_id)
            if ok:
                self.logger.info("MainWindow", f"删除日志 ID={log_id}, Callsign={callsign}")
                QMessageBox.information(self, "成功", msg)
                self.load_logs()
            else:
                self.logger.error("MainWindow", f"删除日志失败: {msg}")
                QMessageBox.warning(self, "失败", msg)

    def open_qrz_lookup_for_callsign(self, callsign: str):
        dialog = QRZLookupDialog(callsign=callsign, parent=self)
        dialog.apply_info.connect(self.on_qrz_info_applied)
        dialog.exec()

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.theme_changed.connect(self.on_theme_changed)
        dialog.intertime_settings_changed.connect(self.restart_intertime)
        dialog.exec()

    # === 新增：打开字体设置 ===
    def open_font_settings(self):
        dialog = FontSettingsDialog(self.settings, self)
        result = dialog.exec()
        # 只有点击保存（Accepted）后才刷新字体
        if result == QDialog.DialogCode.Accepted:
            self._init_font_settings()
            self.load_logs()

    # === 新增：打开代理设置 ===
    def open_proxy_settings(self):
        dialog = ProxySettingsDialog(self.settings, self)
        dialog.exec()

    # === 新增：打开日志查看器 ===
    def open_log_viewer(self):
        dialog = LogViewerDialog(self)
        dialog.exec()

    def on_settings_changed(self):
        self.load_station_info()
        self.load_logs()

    def on_theme_changed(self, new_theme):
        self.current_theme = new_theme
        self.apply_theme()
        self.apply_window_effect()

    def show_about(self):
        from PyQt6.QtCore import QT_VERSION_STR
        import sqlite3
        
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        os_info = f"{platform.system()} {platform.release()}"
        arch = platform.machine()
        
        try:
            total_qso = len(self.db.get_all())
        except:
            total_qso = 0
        
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 HamLog")
        dialog.setMinimumWidth(900)
        dialog.setMinimumHeight(520)
        dialog.resize(1000, 560)
        
        layout = QHBoxLayout(dialog)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ===== 左侧品牌区 =====
        left = QWidget()
        left.setObjectName("about_left")
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(16)
        left_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("HamLog")
        title.setStyleSheet("font-size: 36px; font-weight: bold; color: #4fc3f7;")
        left_layout.addWidget(title)
        
        subtitle = QLabel("业余无线电台日志管理系统")
        subtitle.setStyleSheet("font-size: 16px; color: #888; margin-bottom: 8px;")
        left_layout.addWidget(subtitle)
        
        info_card = QWidget()
        info_card.setStyleSheet("background: #252525; border-radius: 8px;")
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(16, 16, 16, 16)
        
        def info_row(label, value, color="#ffb74d"):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #888; font-size: 13px;")
            val = QLabel(value)
            val.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            return row
        
        info_layout.addLayout(info_row("版本:", CURRENT_VERSION))
        info_layout.addLayout(info_row("构建日期:", "2026-07-15"))
        info_layout.addLayout(info_row("当前QSO:", f"{total_qso} 条", "#81c784"))
        info_layout.addLayout(info_row("协议:", "GPL 3.0 License", "#4fc3f7"))
        left_layout.addWidget(info_card)
        
        left_layout.addStretch()
        
        sign = QLabel("73 DE BA8AQA")
        sign.setStyleSheet("font-size: 20px; color: #4fc3f7; font-weight: bold;")
        sign.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(sign)
        
        dx = QLabel("Best 73 and Good DX!")
        dx.setStyleSheet("font-size: 13px; color: #666;")
        dx.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(dx)
        
        copy = QLabel("@Copyright,HamLog Team,2026")
        copy.setStyleSheet("font-size: 11px; color: #444;")
        copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(copy)
        
        layout.addWidget(left, stretch=4)
        
        # ===== 右侧详情区 =====
        right = QWidget()
        right.setObjectName("about_right")
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(16)
        right_layout.setContentsMargins(30, 30, 30, 30)
        
        feat_title = QLabel("主要功能")
        feat_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #81c784;")
        right_layout.addWidget(feat_title)
        
        feat_text = QLabel("QSO日志记录与管理  |  ADIF导出与LoTW上传  |  QRZ.com呼号查询\n"
                          "网络延迟实时监测  |  代理设置支持  |  深色/浅色主题\n"
                          "自定义字体与界面  |  自动更新检查")
        feat_text.setStyleSheet("color: #aaa; font-size: 12px; line-height: 1.8;")
        feat_text.setWordWrap(True)
        right_layout.addWidget(feat_text)
        
        tech_title = QLabel("技术栈")
        tech_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #81c784; margin-top: 8px;")
        right_layout.addWidget(tech_title)
        
        tech_text = QLabel(f"PyQt6 (Qt {QT_VERSION_STR})  |  SQLite3 ({sqlite3.sqlite_version})  |  Python {py_ver}\n"
                          f"{os_info} ({arch})")
        tech_text.setStyleSheet("color: #aaa; font-size: 12px;")
        tech_text.setWordWrap(True)
        right_layout.addWidget(tech_text)
        
        team_title = QLabel("核心团队")
        team_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #81c784; margin-top: 8px;")
        right_layout.addWidget(team_title)
        
        team_text = QLabel("主要开发者: BA8AQA\n"
                          "贡献者: 开源社区\n")
        team_text.setStyleSheet("color: #aaa; font-size: 12px; line-height: 1.8;")
        team_text.setWordWrap(True)
        right_layout.addWidget(team_text)
        
        link_title = QLabel("相关链接")
        link_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #81c784; margin-top: 8px;")
        right_layout.addWidget(link_title)
        
        links_layout = QVBoxLayout()
        links_layout.setSpacing(4)
        
        def make_link(text, url):
            lbl = QLabel(f'<a href="{url}" style="color: #4fc3f7; text-decoration: none;">{text}</a>')
            lbl.setOpenExternalLinks(True)
            lbl.setStyleSheet("font-size: 12px;")
            return lbl
        
        links_layout.addWidget(make_link("GitHub仓库", "https://github.com/ARPRC-BA8AQA/HamLog"))
        links_layout.addWidget(make_link("Bilibili主页", "https://space.bilibili.com/1297822096"))
        links_layout.addWidget(make_link("ARRL LoTW", "https://lotw.arrl.org"))
        links_layout.addWidget(make_link("QRZ.com", "https://www.qrz.com"))
        right_layout.addLayout(links_layout)
        
        right_layout.addStretch()
        
        disclaimer = QLabel("本软件按原样提供，不提供任何形式的担保。HamLog与ARRL、QRZ.com等第三方服务无任何官方关联。")
        disclaimer.setStyleSheet("color: #666; font-size: 11px; background: #252525; padding: 10px; border-radius: 6px;")
        disclaimer.setWordWrap(True)
        right_layout.addWidget(disclaimer)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.setFixedWidth(100)
        btn_ok.setFixedHeight(36)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #14919b; }
        """)
        btn_ok.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_ok)
        right_layout.addLayout(btn_layout)
        
        layout.addWidget(right, stretch=6)
        
        if self.current_theme == 'dark':
            dialog.setStyleSheet("""
                QDialog { background-color: #1e1e1e; }
                #about_left { background-color: #1a1a1a; }
                #about_right { background-color: #1e1e1e; }
                QLabel { color: #e0e0e0; }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog { background-color: #f5f5f5; }
                #about_left { background-color: #eeeeee; }
                #about_right { background-color: #f5f5f5; }
                QLabel { color: #333; }
            """)
        
        dialog.exec()
    def clear_database(self):
        reply = QMessageBox.warning(
            self,
            "警告",
            "这会永久清空所有日志和配置文件，无法恢复！\n\n确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            confirm = QMessageBox.critical(
                self,
                "最终确认",
                "此操作不可撤销！\n所有 QSO 日志、设置将全部丢失。\n\n确定清空吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    self.db.close()
                    self.settings.close()

                    db_file = Path(self.db.db_path)
                    if db_file.exists():
                        db_file.unlink()

                    self.db = Database()
                    self.settings = SettingsManager()

                    self.load_logs()
                    self.load_station_info()

                    QMessageBox.information(self, "完成", "数据库已清空并重新初始化。")

                except Exception as e:
                    QMessageBox.critical(self, "错误", f"清空失败:\n{e}")
                    try:
                        self.db = Database()
                        self.settings = SettingsManager()
                    except:
                        pass

    def check_update_manual(self):
        self.statusbar.showMessage("正在检查更新...")
        self.update_manager.check_update(silent=False)

    def closeEvent(self, event):
        self.logger.info("MainWindow", "应用程序关闭")
        if self.intertime_worker and self.intertime_worker.isRunning():
            self.intertime_worker.stop()
        if self.intertime_timer:
            self.intertime_timer.stop()
        self.db.close()
        self.settings.close()
        event.accept()

    def init_intertime(self):
        self.intertime_enabled = self.settings.get('intertime_enabled', '1') == '1'
        raw_nodes = self.settings.get('intertime_nodes', 'www.baidu.com')
        self.intertime_node_entries = [n.strip() for n in raw_nodes.split(',') if n.strip()][:5]

        self.intertime_nodes = []
        for entry in self.intertime_node_entries:
            if ' (' in entry and entry.endswith(')'):
                addr = entry.split(' (')[0]
            else:
                addr = entry
            self.intertime_nodes.append(addr)

        self.intertime_timeout = int(self.settings.get('intertime_timeout', '2') or '2')
        self.intertime_interval = int(self.settings.get('intertime_interval', '5') or '5')

        self.intertime_timer = QTimer(self)
        self.intertime_timer.timeout.connect(self._start_intertime_worker)

        if self.intertime_enabled and self.intertime_nodes:
            self.intertime_timer.start(self.intertime_interval * 1000)
            self._start_intertime_worker()
        else:
            self.intertime_label.setText("已关闭")
            self.intertime_label.setStyleSheet("color: #666;")
            self.intertime_icon.setStyleSheet("color: #666; font-size: 10px;")

    def _start_intertime_worker(self):
        if not self.intertime_enabled or not self.intertime_nodes:
            return
        if self.intertime_worker and self.intertime_worker.isRunning():
            return
        self.intertime_worker = IntertimeWorker(self.intertime_nodes, self.intertime_timeout)
        self.intertime_worker.result_ready.connect(self._on_intertime_result)
        self.intertime_worker.start()

    def _on_intertime_result(self, results):
        if not self.intertime_enabled:
            return

        node_entries = self.intertime_node_entries
        nodes_with_alias = []
        for entry in node_entries:
            if ' (' in entry and entry.endswith(')'):
                addr = entry.split(' (')[0]
                alias = entry[entry.rfind(' (')+2:-1]
            else:
                addr = entry
                alias = None
            nodes_with_alias.append((addr, alias))

        parts = []
        all_ok = True
        for i, (node, ok, val) in enumerate(results):
            if i < len(nodes_with_alias):
                addr, alias = nodes_with_alias[i]
                display_name = alias if alias else addr.replace('www.', '').replace('.com', '')
            else:
                display_name = node.replace('www.', '').replace('.com', '')
            display_name = display_name[:10] + '..' if len(display_name) > 10 else display_name
            if ok:
                parts.append(f"{display_name} {val}ms")
            else:
                parts.append(f"{display_name} --")
                all_ok = False

        text = " | ".join(parts)
        self.intertime_label.setText(text)

        if all_ok:
            self.intertime_label.setStyleSheet("color: #81c784;")
            self.intertime_icon.setStyleSheet("color: #4caf50; font-size: 10px;")
        else:
            self.intertime_label.setStyleSheet("color: #ffb74d;")
            self.intertime_icon.setStyleSheet("color: #ff9800; font-size: 10px;")

    def restart_intertime(self):
        if self.intertime_worker and self.intertime_worker.isRunning():
            self.intertime_worker.stop()
        if self.intertime_timer:
            self.intertime_timer.stop()
        self.init_intertime()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
