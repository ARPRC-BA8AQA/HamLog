# -*- coding: utf-8 -*-
"""
HAMLOG GUI - 业余无线电台日志管理系统前端界面
使用 PyQt6 构建
"""
import pkgutil  # PyInstaller: 强制收集，防止打包后缺失
import sys
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QMessageBox, QComboBox, QSpinBox, QGroupBox, QGridLayout,
    QHeaderView, QFrame, QTextEdit, QMenu, QStatusBar, QFormLayout, QScrollArea,
    QCheckBox, QListWidget, QInputDialog)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QAction, QKeySequence, QDesktopServices
from ADIF_Export_Dialog import ADIFExportDialog
from LoTW_Upload_Dialog import LoTWUploadDialog
from AutoDeal import Database, SettingsManager, Validator
import os
import platform
from pathlib import Path
from intertime import get_ping_time, get_multi_ping_times


class StyleSheet:
    """样式表"""
    DARK = """
    QMainWindow {
        background-color: #1e1e1e;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
        font-family: "Microsoft YaHei", "SimHei", sans-serif;
        font-size: 13px;
    }
    QGroupBox {
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #4fc3f7;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit {
        background-color: #2d2d2d;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 6px 10px;
        color: #e0e0e0;
        selection-background-color: #4fc3f7;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
        border: 1px solid #4fc3f7;
    }
    QLineEdit:disabled {
        background-color: #252525;
        color: #666;
    }
    QPushButton {
        background-color: #0d7377;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #14919b;
    }
    QPushButton:pressed {
        background-color: #0a5c5f;
    }
    QPushButton:disabled {
        background-color: #333;
        color: #666;
    }
    QPushButton#danger {
        background-color: #c62828;
    }
    QPushButton#danger:hover {
        background-color: #e53935;
    }
    QPushButton#success {
        background-color: #2e7d32;
    }
    QPushButton#success:hover {
        background-color: #43a047;
    }
    QTableWidget {
        background-color: #252525;
        border: 1px solid #3c3c3c;
        gridline-color: #3c3c3c;
        selection-background-color: #0d7377;
        selection-color: white;
    }
    QTableWidget::item {
        padding: 6px;
        border-bottom: 1px solid #3c3c3c;
    }
    QTableWidget::item:selected {
        background-color: #0d7377;
    }
    QHeaderView::section {
        background-color: #2d2d2d;
        color: #4fc3f7;
        padding: 8px;
        border: none;
        border-right: 1px solid #3c3c3c;
        font-weight: bold;
    }
    QTabWidget::pane {
        border: 1px solid #3c3c3c;
        background-color: #1e1e1e;
    }
    QTabBar::tab {
        background-color: #2d2d2d;
        color: #aaa;
        padding: 10px 20px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #0d7377;
        color: white;
    }
    QTabBar::tab:hover:!selected {
        background-color: #3c3c3c;
        color: #e0e0e0;
    }
    QMenuBar {
        background-color: #2d2d2d;
        color: #e0e0e0;
    }
    QMenuBar::item:selected {
        background-color: #0d7377;
    }
    QMenu {
        background-color: #2d2d2d;
        border: 1px solid #3c3c3c;
    }
    QMenu::item:selected {
        background-color: #0d7377;
    }
    QStatusBar {
        background-color: #2d2d2d;
        color: #aaa;
    }
    QScrollArea {
        border: none;
    }
    QLabel#title {
        font-size: 24px;
        font-weight: bold;
        color: #4fc3f7;
    }
    QLabel#subtitle {
        font-size: 14px;
        color: #aaa;
    }
    QLabel#clock {
        font-size: 28px;
        font-weight: bold;
        color: #4fc3f7;
        font-family: "Consolas", "Courier New", monospace;
    }
    QLabel#date {
        font-size: 16px;
        color: #aaa;
    }
    QLabel#info_label {
        color: #81c784;
        font-weight: bold;
    }
    QLabel#error_label {
        color: #e57373;
        font-weight: bold;
    }
    QLabel#webtime {
        font-size: 12px;
        font-family: "Consolas", "Courier New", monospace;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        background-color: #2d2d2d;
        color: #e0e0e0;
        selection-background-color: #0d7377;
    }
    """

    LIGHT = """
    QMainWindow {
        background-color: #f5f5f5;
    }
    QWidget {
        background-color: #f5f5f5;
        color: #333333;
        font-family: "Microsoft YaHei", "SimHei", sans-serif;
        font-size: 13px;
    }
    QGroupBox {
        border: 1px solid #cccccc;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #1565c0;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit {
        background-color: #ffffff;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 6px 10px;
        color: #333333;
        selection-background-color: #1976d2;
        selection-color: white;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
        border: 1px solid #1976d2;
    }
    QLineEdit:disabled {
        background-color: #eeeeee;
        color: #999999;
    }
    QPushButton {
        background-color: #1976d2;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #1565c0;
    }
    QPushButton:pressed {
        background-color: #0d47a1;
    }
    QPushButton:disabled {
        background-color: #bdbdbd;
        color: #757575;
    }
    QPushButton#danger {
        background-color: #c62828;
    }
    QPushButton#danger:hover {
        background-color: #b71c1c;
    }
    QPushButton#success {
        background-color: #2e7d32;
    }
    QPushButton#success:hover {
        background-color: #1b5e20;
    }
    QTableWidget {
        background-color: #ffffff;
        border: 1px solid #cccccc;
        gridline-color: #e0e0e0;
        selection-background-color: #1976d2;
        selection-color: white;
    }
    QTableWidget::item {
        padding: 6px;
        border-bottom: 1px solid #e0e0e0;
    }
    QTableWidget::item:selected {
        background-color: #1976d2;
    }
    QHeaderView::section {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 8px;
        border: none;
        border-right: 1px solid #cccccc;
        font-weight: bold;
    }
    QTabWidget::pane {
        border: 1px solid #cccccc;
        background-color: #f5f5f5;
    }
    QTabBar::tab {
        background-color: #e0e0e0;
        color: #666666;
        padding: 10px 20px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #1976d2;
        color: white;
    }
    QTabBar::tab:hover:!selected {
        background-color: #bdbdbd;
        color: #333333;
    }
    QMenuBar {
        background-color: #e3f2fd;
        color: #333333;
    }
    QMenuBar::item:selected {
        background-color: #1976d2;
        color: white;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #cccccc;
    }
    QMenu::item:selected {
        background-color: #1976d2;
        color: white;
    }
    QStatusBar {
        background-color: #e3f2fd;
        color: #666666;
    }
    QScrollArea {
        border: none;
    }
    QLabel#title {
        font-size: 24px;
        font-weight: bold;
        color: #1565c0;
    }
    QLabel#subtitle {
        font-size: 14px;
        color: #666666;
    }
    QLabel#clock {
        font-size: 28px;
        font-weight: bold;
        color: #1565c0;
        font-family: "Consolas", "Courier New", monospace;
    }
    QLabel#date {
        font-size: 16px;
        color: #666666;
    }
    QLabel#info_label {
        color: #2e7d32;
        font-weight: bold;
    }
    QLabel#error_label {
        color: #c62828;
        font-weight: bold;
    }
    QLabel#webtime {
        font-size: 12px;
        font-family: "Consolas", "Courier New", monospace;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        color: #333333;
        selection-background-color: #1976d2;
    }
    """


class LogDialog(QDialog):
    """日志编辑对话框"""

    log_saved = pyqtSignal()

    def __init__(self, mode="add", log_data=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.log_data = log_data or {}
        self.settings = SettingsManager()
        self.init_ui()
        self.load_defaults()

    def init_ui(self):
        if self.mode == "add":
            self.setWindowTitle("添加日志")
        elif self.mode == "edit":
            self.setWindowTitle("编辑日志")
        else:
            self.setWindowTitle("查看日志")

        self.setMinimumSize(1100, 700)
        self.resize(1200, 800)

        # 根据父窗口主题设置样式
        parent_theme = 'dark'
        if self.parent() and hasattr(self.parent(), 'current_theme'):
            parent_theme = self.parent().current_theme
        self.setStyleSheet(StyleSheet.DARK if parent_theme == 'dark' else StyleSheet.LIGHT)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("日志记录")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        # === 改为两列主布局 ===
        main_grid = QGridLayout(content_widget)
        main_grid.setSpacing(20)
        main_grid.setContentsMargins(10, 10, 10, 10)
        main_grid.setColumnStretch(0, 1)
        main_grid.setColumnStretch(1, 1)

        # ========== 左列 ==========
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # --- 基本信息组 (左列上半) ---
        basic_group = QGroupBox("基本信息")
        basic_layout = QGridLayout(basic_group)
        basic_layout.setSpacing(10)
        basic_layout.setContentsMargins(15, 20, 15, 15)

        # 呼号
        basic_layout.addWidget(QLabel("对方呼号*："), 0, 0)
        self.callsign_edit = QLineEdit()
        self.callsign_edit.setPlaceholderText("呼号")
        self.callsign_edit.setMaxLength(10)
        basic_layout.addWidget(self.callsign_edit, 0, 1, 1, 2)

        # 频率
        basic_layout.addWidget(QLabel("频率："), 1, 0)
        self.freq_edit = QLineEdit()
        self.freq_edit.setPlaceholderText("如：144.000MHz")
        basic_layout.addWidget(self.freq_edit, 1, 1, 1, 2)

        # 日期
        basic_layout.addWidget(QLabel("日期*："), 2, 0)
        date_layout = QHBoxLayout()
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(datetime.now().month)
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(datetime.now().day)
        date_layout.addWidget(self.year_spin)
        date_layout.addWidget(QLabel("年"))
        date_layout.addWidget(self.month_spin)
        date_layout.addWidget(QLabel("月"))
        date_layout.addWidget(self.day_spin)
        date_layout.addWidget(QLabel("日"))
        date_layout.addStretch()
        basic_layout.addLayout(date_layout, 2, 1, 1, 2)

        # 时区
        basic_layout.addWidget(QLabel("时区*："), 3, 0)
        self.tz_combo = QComboBox()
        self.tz_combo.addItem("UTC", "utc")
        self.tz_combo.addItem("北京时间 (UTC+8)", "bjs")
        self.tz_combo.currentIndexChanged.connect(self.on_tz_changed)
        basic_layout.addWidget(self.tz_combo, 3, 1)

        # 时间
        basic_layout.addWidget(QLabel("时间*："), 4, 0)
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_layout.setSpacing(8)
        time_layout.setContentsMargins(0, 0, 0, 0)
        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HHMM（如：1316）")
        self.time_edit.setMaxLength(4)
        self.time_edit.setFixedWidth(80)
        now_time = datetime.now().strftime("%H%M")
        self.time_edit.setText(now_time)
        time_layout.addWidget(self.time_edit)
        self.utc_preview_label = QLabel("")
        self.utc_preview_label.setStyleSheet("color: #888; font-size: 11px;")
        time_layout.addWidget(self.utc_preview_label)
        time_layout.addStretch()
        basic_layout.addWidget(time_widget, 4, 1, 1, 2)

        # 时间提示
        self.time_hint = QLabel("保存时自动转换为 UTC 时间")
        self.time_hint.setStyleSheet("color: #4fc3f7; font-size: 11px;")
        basic_layout.addWidget(self.time_hint, 5, 1, 1, 2)

        # 模式
        basic_layout.addWidget(QLabel("模式*："), 6, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["FM", "SSB", "CW", "AM", "FT8", "FT4", "JT65", "PSK", "RTTY", "SSTV", "其他"])
        self.mode_combo.setEditable(True)
        basic_layout.addWidget(self.mode_combo, 6, 1)

        # QTH
        basic_layout.addWidget(QLabel("QTH："), 7, 0)
        self.qth_edit = QLineEdit()
        self.qth_edit.setPlaceholderText("通联地点")
        basic_layout.addWidget(self.qth_edit, 7, 1, 1, 2)

        left_layout.addWidget(basic_group)

        # --- 信号报告组 (左列下半) ---
        rst_group = QGroupBox("信号报告")
        rst_layout = QGridLayout(rst_group)
        rst_layout.setSpacing(10)
        rst_layout.setContentsMargins(15, 20, 15, 15)

        rst_layout.addWidget(QLabel("对方给我*："), 0, 0)
        self.rst_self_edit = QLineEdit()
        self.rst_self_edit.setPlaceholderText("如：59")
        self.rst_self_edit.setMaxLength(3)
        self.rst_self_edit.setFixedWidth(80)
        rst_layout.addWidget(self.rst_self_edit, 0, 1)
        rst_layout.addWidget(QLabel("（他听我）"), 0, 2)

        rst_layout.addWidget(QLabel("我给对方*："), 1, 0)
        self.rst_side_edit = QLineEdit()
        self.rst_side_edit.setPlaceholderText("如：58")
        self.rst_side_edit.setMaxLength(3)
        self.rst_side_edit.setFixedWidth(80)
        rst_layout.addWidget(self.rst_side_edit, 1, 1)
        rst_layout.addWidget(QLabel("（我听他）"), 1, 2)
        rst_layout.setColumnStretch(3, 1)

        left_layout.addWidget(rst_group)
        left_layout.addStretch()

        main_grid.addLayout(left_layout, 0, 0)

        # ========== 右列 ==========
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # --- 功率与设备组 (右列上半) ---
        power_group = QGroupBox("功率与设备")
        power_layout = QGridLayout(power_group)
        power_layout.setSpacing(10)
        power_layout.setContentsMargins(15, 20, 15, 15)

        power_layout.addWidget(QLabel("我的功率*："), 0, 0)
        self.power_self_edit = QLineEdit()
        self.power_self_edit.setPlaceholderText("如：5W")
        self.power_self_edit.setFixedWidth(100)
        power_layout.addWidget(self.power_self_edit, 0, 1)
        power_layout.addWidget(QLabel("对方功率："), 0, 2)
        self.power_side_edit = QLineEdit()
        self.power_side_edit.setPlaceholderText("如：8W")
        self.power_side_edit.setFixedWidth(100)
        power_layout.addWidget(self.power_side_edit, 0, 3)
        power_layout.setColumnStretch(4, 1)

        power_layout.addWidget(QLabel("设备："), 1, 0)
        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("使用的设备型号")
        power_layout.addWidget(self.device_edit, 1, 1, 1, 4)

        right_layout.addWidget(power_group)

        # --- QSL 卡片组 (右列中) ---
        qsl_group = QGroupBox("QSL 卡片")
        qsl_layout = QGridLayout(qsl_group)
        qsl_layout.setSpacing(10)
        qsl_layout.setContentsMargins(15, 20, 15, 15)

        qsl_layout.addWidget(QLabel("收到QSL："), 0, 0)
        self.qsl_rx_edit = QLineEdit()
        self.qsl_rx_edit.setPlaceholderText("YYYYMMDD（如：20260612）")
        self.qsl_rx_edit.setMaxLength(8)
        qsl_layout.addWidget(self.qsl_rx_edit, 0, 1)

        qsl_layout.addWidget(QLabel("发出QSL："), 1, 0)
        self.qsl_send_edit = QLineEdit()
        self.qsl_send_edit.setPlaceholderText("YYYYMMDD（如：20260620）")
        self.qsl_send_edit.setMaxLength(8)
        qsl_layout.addWidget(self.qsl_send_edit, 1, 1)
        qsl_layout.setColumnStretch(2, 1)

        right_layout.addWidget(qsl_group)

        # --- 备注组 (右列下半) ---
        remark_group = QGroupBox("备注")
        remark_layout = QVBoxLayout(remark_group)
        remark_layout.setContentsMargins(15, 20, 15, 15)
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMinimumHeight(100)
        self.remarks_edit.setPlaceholderText("其他备注信息...")
        remark_layout.addWidget(self.remarks_edit)

        right_layout.addWidget(remark_group)
        right_layout.addStretch()

        main_grid.addLayout(right_layout, 0, 1)

        # 错误提示（跨两列底部）
        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_grid.addWidget(self.error_label, 1, 0, 1, 2)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 按钮
        btn_layout = QHBoxLayout()

        if self.mode in ("add", "edit"):
            self.save_btn = QPushButton("保存")
            self.save_btn.setObjectName("success")
            self.save_btn.clicked.connect(self.save_log)
            btn_layout.addWidget(self.save_btn)

        if self.mode == "edit":
            self.delete_btn = QPushButton("删除")
            self.delete_btn.setObjectName("danger")
            self.delete_btn.clicked.connect(self.delete_log)
            btn_layout.addWidget(self.delete_btn)

        self.cancel_btn = QPushButton("关闭")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # 查看模式禁用所有输入
        if self.mode == "view":
            for widget in [
                self.callsign_edit, self.freq_edit, self.year_spin, self.month_spin,
                self.day_spin, self.time_edit, self.mode_combo, self.qth_edit,
                self.rst_self_edit, self.rst_side_edit, self.power_self_edit,
                self.power_side_edit, self.device_edit, self.qsl_rx_edit,
                self.qsl_send_edit, self.remarks_edit, self.tz_combo
            ]:
                widget.setEnabled(False)
            self.utc_preview_label.setVisible(False)
            self.time_hint.setText("数据库统一存储 UTC 时间")

        # 编辑模式禁用时间和时区（不允许修改）
        if self.mode == "edit":
            for widget in [self.year_spin, self.month_spin, self.day_spin, self.time_edit, self.tz_combo]:
                widget.setEnabled(False)
            self.utc_preview_label.setVisible(False)
            self.time_hint.setText("编辑模式不允许修改时间")

        if self.log_data:
            self.load_data()

    def load_defaults(self):
        default_mode = self.settings.get('default_mode', 'FM')
        default_power = self.settings.get('default_power', '5W')
        default_device = self.settings.get('default_device', 'UVK6')

        self.mode_combo.setCurrentText(default_mode)
        self.power_self_edit.setText(default_power)
        self.device_edit.setText(default_device)

    def on_tz_changed(self, index):
        """时区切换时更新 UTC 预览"""
        self.update_utc_preview()

    def update_utc_preview(self):
        """更新 UTC 时间预览"""
        if self.mode != "add":
            return
        try:
            year = self.year_spin.value()
            month = self.month_spin.value()
            day = self.day_spin.value()
            time_str = self.time_edit.text().strip()
            if len(time_str) == 4 and time_str.isdigit():
                hour = int(time_str[:2])
                minute = int(time_str[2:])
                from datetime import datetime, timezone, timedelta
                dt = datetime(year, month, day, hour, minute)
                tz_type = self.tz_combo.currentData()
                if tz_type == "bjs":
                    # 北京时间转 UTC
                    dt_utc = dt - timedelta(hours=8)
                    self.utc_preview_label.setText(f"→ UTC {dt_utc.strftime('%H%M')}")
                else:
                    self.utc_preview_label.setText("(UTC)")
            else:
                self.utc_preview_label.setText("")
        except:
            self.utc_preview_label.setText("")

    def convert_to_utc(self, year, month, day, time_str, tz_type):
        """将用户输入的时间转换为 UTC

        :param tz_type: 'utc' 或 'bjs'
        :return: (utc_year, utc_month, utc_day, utc_time_str)
        """
        from datetime import datetime, timedelta
        if len(time_str) != 4 or not time_str.isdigit():
            return year, month, day, time_str
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        dt = datetime(year, month, day, hour, minute)
        if tz_type == "bjs":
            dt = dt - timedelta(hours=8)
        return dt.year, dt.month, dt.day, dt.strftime("%H%M")

    def convert_from_utc_to_bjs(self, year, month, day, time_str):
        """将 UTC 时间转换为北京时间（用于显示）"""
        from datetime import datetime, timedelta
        if len(time_str) != 4 or not time_str.isdigit():
            return year, month, day, time_str
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        dt = datetime(year, month, day, hour, minute)
        dt_bjs = dt + timedelta(hours=8)
        return dt_bjs.year, dt_bjs.month, dt_bjs.day, dt_bjs.strftime("%H%M")

    def load_data(self):
        self.callsign_edit.setText(self.log_data.get('Callsign', ''))
        self.freq_edit.setText(self.log_data.get('Freq', ''))

        # 数据库统一存 UTC，显示时转换为北京时间
        year = self.log_data.get('Year', datetime.now().year)
        month = self.log_data.get('Month', datetime.now().month)
        day = self.log_data.get('Day', datetime.now().day)
        time_str = self.log_data.get('Time', '')

        # UTC 转北京时间显示
        bjs_year, bjs_month, bjs_day, bjs_time = self.convert_from_utc_to_bjs(year, month, day, time_str)
        self.year_spin.setValue(bjs_year)
        self.month_spin.setValue(bjs_month)
        self.day_spin.setValue(bjs_day)
        self.time_edit.setText(bjs_time)

        self.mode_combo.setCurrentText(self.log_data.get('Mode', 'FM'))
        self.qth_edit.setText(self.log_data.get('QTH', ''))
        self.rst_self_edit.setText(self.log_data.get('Rst_self', ''))
        self.rst_side_edit.setText(self.log_data.get('Rst_side', ''))
        self.power_self_edit.setText(self.log_data.get('Power_self', ''))
        self.power_side_edit.setText(self.log_data.get('Power_side', ''))
        self.device_edit.setText(self.log_data.get('Device', ''))
        self.qsl_rx_edit.setText(self.log_data.get('QSL_RX', ''))
        self.qsl_send_edit.setText(self.log_data.get('QSL_SEND', ''))
        self.remarks_edit.setPlainText(self.log_data.get('Remarks', ''))

    def validate_inputs(self):
        errors = []

        ok, result = Validator.validate_callsign(self.callsign_edit.text())
        if not ok:
            errors.append("呼号：" + result)
        else:
            self.callsign_edit.setText(result)

        ok, result = Validator.validate_date(
            self.year_spin.value(),
            self.month_spin.value(),
            self.day_spin.value()
        )
        if not ok:
            errors.append("日期：" + result)

        ok, result = Validator.validate_time(self.time_edit.text())
        if not ok:
            errors.append("时间：" + result)
        else:
            self.time_edit.setText(result)
            # 时间有效时更新 UTC 预览
            self.update_utc_preview()

        if not self.mode_combo.currentText().strip():
            errors.append("模式：不能为空")

        ok, result = Validator.validate_rst(self.rst_self_edit.text())
        if not ok:
            errors.append("对方给我报告：" + result)
        else:
            self.rst_self_edit.setText(result)

        ok, result = Validator.validate_rst(self.rst_side_edit.text())
        if not ok:
            errors.append("我给对方报告：" + result)
        else:
            self.rst_side_edit.setText(result)

        ok, result = Validator.validate_power(self.power_self_edit.text())
        if not ok:
            errors.append("我的功率：" + result)
        else:
            self.power_self_edit.setText(result)

        if self.power_side_edit.text().strip():
            ok, result = Validator.validate_power(self.power_side_edit.text())
            if not ok:
                errors.append("对方功率：" + result)
            else:
                self.power_side_edit.setText(result)

        ok, result = Validator.validate_freq(self.freq_edit.text())
        if not ok:
            errors.append("频率：" + result)
        else:
            self.freq_edit.setText(result)

        ok, result = Validator.validate_qsl_date(self.qsl_rx_edit.text())
        if not ok:
            errors.append("收到QSL：" + result)
        else:
            self.qsl_rx_edit.setText(result)

        ok, result = Validator.validate_qsl_date(self.qsl_send_edit.text())
        if not ok:
            errors.append("发出QSL：" + result)
        else:
            self.qsl_send_edit.setText(result)

        if errors:
            self.error_label.setText("\n".join(errors))
            return False

        self.error_label.setText("")
        return True

    def save_log(self):
        if not self.validate_inputs():
            return

        # 添加模式：根据时区选择转换为 UTC
        if self.mode == "add":
            tz_type = self.tz_combo.currentData()
            utc_year, utc_month, utc_day, utc_time = self.convert_to_utc(
                self.year_spin.value(),
                self.month_spin.value(),
                self.day_spin.value(),
                self.time_edit.text().strip(),
                tz_type
            )
        else:
            # 编辑模式：时间不变，保持原UTC值
            utc_year = self.year_spin.value()
            utc_month = self.month_spin.value()
            utc_day = self.day_spin.value()
            utc_time = self.time_edit.text().strip()

        log_dict = {
            'Callsign': self.callsign_edit.text().strip().upper(),
            'Freq': self.freq_edit.text().strip(),
            'Year': utc_year,
            'Month': utc_month,
            'Day': utc_day,
            'Time': utc_time,
            'Mode': self.mode_combo.currentText().strip(),
            'Power_self': self.power_self_edit.text().strip(),
            'Power_side': self.power_side_edit.text().strip(),
            'Rst_self': self.rst_self_edit.text().strip(),
            'Rst_side': self.rst_side_edit.text().strip(),
            'QTH': self.qth_edit.text().strip(),
            'Device': self.device_edit.text().strip(),
            'QSL_RX': self.qsl_rx_edit.text().strip(),
            'QSL_SEND': self.qsl_send_edit.text().strip(),
            'Remarks': self.remarks_edit.toPlainText().strip()
        }

        db = Database()
        try:
            if self.mode == "add":
                ok, msg = db.add(log_dict)
            else:
                log_id = self.log_data.get('id')
                ok, msg = db.update(log_id, log_dict)

            if ok:
                QMessageBox.information(self, "成功", msg)
                self.log_saved.emit()
                self.accept()
            else:
                QMessageBox.warning(self, "失败", msg)
        finally:
            db.close()

    def delete_log(self):
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除与 " + self.log_data.get('Callsign', '') + " 的通联记录吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            db = Database()
            try:
                ok, msg = db.delete(self.log_data.get('id'))
                if ok:
                    QMessageBox.information(self, "成功", msg)
                    self.log_saved.emit()
                    self.accept()
                else:
                    QMessageBox.warning(self, "失败", msg)
            finally:
                db.close()


class SettingsDialog(QDialog):
    """设置对话框"""

    settings_changed = pyqtSignal()
    theme_changed = pyqtSignal(str)
    intertime_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("设置")
        self.setMinimumSize(950, 620)
        self.resize(1000, 680)

        # 根据父窗口主题设置样式
        parent_theme = 'dark'
        if self.parent() and hasattr(self.parent(), 'current_theme'):
            parent_theme = self.parent().current_theme
        self.setStyleSheet(StyleSheet.DARK if parent_theme == 'dark' else StyleSheet.LIGHT)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("软件设置")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # === 两列主布局 ===
        main_hlayout = QHBoxLayout()
        main_hlayout.setSpacing(20)

        # ---- 左列 ----
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # 本台信息
        info_group = QGroupBox("本台信息")
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(14)
        info_layout.setContentsMargins(18, 18, 18, 18)
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.callsign_edit = QLineEdit()
        self.callsign_edit.setPlaceholderText("呼号")
        self.callsign_edit.setMinimumHeight(28)
        info_layout.addRow("本台呼号：", self.callsign_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("操作员姓名")
        self.name_edit.setMinimumHeight(28)
        info_layout.addRow("操作员：", self.name_edit)

        self.qth_edit = QLineEdit()
        self.qth_edit.setPlaceholderText("常用QTH")
        self.qth_edit.setMinimumHeight(28)
        info_layout.addRow("常用QTH：", self.qth_edit)

        self.grid_edit = QLineEdit()
        self.grid_edit.setPlaceholderText("网格定位（如：OM66）")
        self.grid_edit.setMinimumHeight(28)
        info_layout.addRow("网格定位：", self.grid_edit)

        left_layout.addWidget(info_group)

        # 默认参数
        default_group = QGroupBox("默认参数")
        default_layout = QFormLayout(default_group)
        default_layout.setSpacing(14)
        default_layout.setContentsMargins(18, 18, 18, 18)
        default_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        default_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["FM", "SSB", "CW", "AM", "FT8", "FT4", "JT65", "PSK", "RTTY", "SSTV"])
        self.mode_combo.setEditable(True)
        self.mode_combo.setMinimumHeight(28)
        default_layout.addRow("默认模式：", self.mode_combo)

        self.power_edit = QLineEdit()
        self.power_edit.setPlaceholderText("如：5W")
        self.power_edit.setMinimumHeight(28)
        default_layout.addRow("默认功率：", self.power_edit)

        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("默认设备型号")
        self.device_edit.setMinimumHeight(28)
        default_layout.addRow("默认设备：", self.device_edit)

        left_layout.addWidget(default_group)
        left_layout.addStretch()

        main_hlayout.addLayout(left_layout, stretch=1)

        # ---- 右列 ----
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # 外观设置
        theme_group = QGroupBox("外观")
        theme_layout = QFormLayout(theme_group)
        theme_layout.setSpacing(14)
        theme_layout.setContentsMargins(18, 18, 18, 18)
        theme_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        theme_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色", "浅色"])
        self.theme_combo.setMinimumHeight(28)
        theme_layout.addRow("主题：", self.theme_combo)

        right_layout.addWidget(theme_group)

        # 网络延迟检测
        intertime_group = QGroupBox("网络延迟检测")
        intertime_layout = QFormLayout(intertime_group)
        intertime_layout.setSpacing(14)
        intertime_layout.setContentsMargins(18, 18, 18, 18)
        intertime_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        intertime_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.intertime_enabled_cb = QCheckBox("启用实时网络延迟检测")
        self.intertime_enabled_cb.setMinimumHeight(24)
        intertime_layout.addRow(self.intertime_enabled_cb)

        # === 节点列表 (QListWidget) ===
        intertime_layout.addRow(QLabel("检测节点 (最多5个):"))

        self.intertime_nodes_list = QListWidget()
        self.intertime_nodes_list.setMaximumHeight(140)
        self.intertime_nodes_list.setMinimumHeight(100)
        self.intertime_nodes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.intertime_nodes_list.customContextMenuRequested.connect(self.show_node_context_menu)
        intertime_layout.addRow(self.intertime_nodes_list)

        # 节点操作按钮
        nodes_btn_layout = QHBoxLayout()
        nodes_btn_layout.setSpacing(8)

        self.btn_add_node = QPushButton("+ 添加")
        self.btn_add_node.setMinimumHeight(28)
        self.btn_add_node.clicked.connect(self.add_intertime_node)
        nodes_btn_layout.addWidget(self.btn_add_node)

        self.btn_remove_node = QPushButton("- 删除")
        self.btn_remove_node.setMinimumHeight(28)
        self.btn_remove_node.clicked.connect(self.remove_intertime_node)
        nodes_btn_layout.addWidget(self.btn_remove_node)

        self.btn_clear_nodes = QPushButton("清空")
        self.btn_clear_nodes.setMinimumHeight(28)
        self.btn_clear_nodes.clicked.connect(self.clear_intertime_nodes)
        nodes_btn_layout.addWidget(self.btn_clear_nodes)
        nodes_btn_layout.addStretch()

        intertime_layout.addRow(nodes_btn_layout)



        timeout_layout = QHBoxLayout()
        self.intertime_timeout_spin = QSpinBox()
        self.intertime_timeout_spin.setRange(1, 10)
        self.intertime_timeout_spin.setSuffix(" 秒")
        self.intertime_timeout_spin.setMinimumHeight(26)
        timeout_layout.addWidget(self.intertime_timeout_spin)
        timeout_layout.addStretch()
        intertime_layout.addRow("超时时间:", timeout_layout)

        interval_layout = QHBoxLayout()
        self.intertime_interval_spin = QSpinBox()
        self.intertime_interval_spin.setRange(3, 60)
        self.intertime_interval_spin.setSuffix(" 秒")
        self.intertime_interval_spin.setMinimumHeight(26)
        interval_layout.addWidget(self.intertime_interval_spin)
        interval_layout.addStretch()
        intertime_layout.addRow("刷新间隔:", interval_layout)

        hint = QLabel("提示: 节点过多或间隔过短可能影响性能")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        intertime_layout.addRow(hint)

        right_layout.addWidget(intertime_group)
        right_layout.addStretch()

        main_hlayout.addLayout(right_layout, stretch=1)

        layout.addLayout(main_hlayout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.setContentsMargins(0, 10, 0, 0)
        btn_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("success")
        self.save_btn.setMinimumWidth(120)
        self.save_btn.setMinimumHeight(38)
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumWidth(120)
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def load_settings(self):
        self.callsign_edit.setText(self.settings.get('my_callsign', ''))
        self.name_edit.setText(self.settings.get('my_name', ''))
        self.qth_edit.setText(self.settings.get('my_qth', ''))
        self.grid_edit.setText(self.settings.get('my_grid', ''))
        self.mode_combo.setCurrentText(self.settings.get('default_mode', 'FM'))
        self.power_edit.setText(self.settings.get('default_power', '5W'))
        self.device_edit.setText(self.settings.get('default_device', 'UVK6'))
        theme = self.settings.get('theme', 'dark')
        self.theme_combo.setCurrentIndex(0 if theme == 'dark' else 1)
        # === 加载网络延迟设置 ===
        self.intertime_enabled_cb.setChecked(self.settings.get('intertime_enabled', '1') == '1')
        # 加载节点列表
        self.intertime_nodes_list.clear()
        raw_nodes = self.settings.get('intertime_nodes', 'www.baidu.com')
        nodes = [n.strip() for n in raw_nodes.split(',') if n.strip()][:5]
        for node in nodes:
            self.intertime_nodes_list.addItem(node)

        self.intertime_timeout_spin.setValue(int(self.settings.get('intertime_timeout', '2') or '2'))
        self.intertime_interval_spin.setValue(int(self.settings.get('intertime_interval', '5') or '5'))

    def save_settings(self):
        self.settings.set('my_callsign', self.callsign_edit.text().strip())
        self.settings.set('my_name', self.name_edit.text().strip())
        self.settings.set('my_qth', self.qth_edit.text().strip())
        self.settings.set('my_grid', self.grid_edit.text().strip())
        self.settings.set('default_mode', self.mode_combo.currentText().strip())
        self.settings.set('default_power', self.power_edit.text().strip())
        self.settings.set('default_device', self.device_edit.text().strip())
        new_theme = 'dark' if self.theme_combo.currentIndex() == 0 else 'light'
        self.settings.set('theme', new_theme)
        # === 保存网络延迟设置 ===
        self.settings.set('intertime_enabled', '1' if self.intertime_enabled_cb.isChecked() else '0')
        # 从 QListWidget 读取节点，最多5个
        nodes = []
        for i in range(self.intertime_nodes_list.count()):
            text = self.intertime_nodes_list.item(i).text().strip()
            if text and text not in nodes:
                nodes.append(text)
        nodes = nodes[:5]
        self.settings.set('intertime_nodes', ','.join(nodes))

        self.settings.set('intertime_timeout', str(self.intertime_timeout_spin.value()))
        self.settings.set('intertime_interval', str(self.intertime_interval_spin.value()))

        self.settings_changed.emit()
        self.theme_changed.emit(new_theme)
        self.intertime_settings_changed.emit()  # 通知主窗口重启延迟检测
        QMessageBox.information(self, "成功", "设置已保存！")
        self.accept()

    def add_intertime_node(self):
        """添加检测节点"""
        if self.intertime_nodes_list.count() >= 5:
            QMessageBox.warning(self, "提示", "最多只能添加5个节点")
            return
        text, ok = QInputDialog.getText(self, "添加节点", "输入域名或IP地址:")
        if ok and text.strip():
            node = text.strip()
            # 检查是否已存在
            for i in range(self.intertime_nodes_list.count()):
                if self.intertime_nodes_list.item(i).text() == node:
                    QMessageBox.warning(self, "提示", "该节点已存在")
                    return
            self.intertime_nodes_list.addItem(node)

    def show_node_context_menu(self, position):
        """节点列表右键菜单"""
        item = self.intertime_nodes_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        edit_action = menu.addAction("编辑IP/域名")
        alias_action = menu.addAction("修改别名")
        delete_action = menu.addAction("删除")

        action = menu.exec(self.intertime_nodes_list.viewport().mapToGlobal(position))

        if action == edit_action:
            self.edit_intertime_node(item)
        elif action == alias_action:
            self.edit_node_alias(item)
        elif action == delete_action:
            self.remove_intertime_node()

    def edit_intertime_node(self, item):
        """编辑选中的节点"""
        old_text = item.text()
        text, ok = QInputDialog.getText(self, "编辑节点", "修改域名或IP地址:", text=old_text)
        if ok and text.strip():
            new_text = text.strip()
            # 检查是否与其他节点重复
            for i in range(self.intertime_nodes_list.count()):
                if i != self.intertime_nodes_list.row(item) and self.intertime_nodes_list.item(i).text() == new_text:
                    QMessageBox.warning(self, "提示", "该节点已存在")
                    return
            item.setText(new_text)

    def edit_node_alias(self, item):
        """修改节点别名"""
        # 获取当前节点的原始地址（去掉可能存在的别名标记）
        full_text = item.text()
        # 如果已有别名格式 "地址 (别名)"，提取地址部分
        if ' (' in full_text and full_text.endswith(')'):
            addr = full_text.split(' (')[0]
        else:
            addr = full_text

        label_text = "为 " + addr + " 设置显示别名:" + chr(10) + "(留空则使用原始地址)"
        alias, ok = QInputDialog.getText(self, "修改别名", label_text, text="")
        if ok:
            alias = alias.strip()
            if alias:
                item.setText(addr + " (" + alias + ")")
            else:
                item.setText(addr)

    def remove_intertime_node(self):
        """删除选中的检测节点"""
        current_row = self.intertime_nodes_list.currentRow()
        if current_row >= 0:
            self.intertime_nodes_list.takeItem(current_row)

    def clear_intertime_nodes(self):
        """清空所有检测节点"""
        self.intertime_nodes_list.clear()




def get_system_proxy():
    """获取系统代理设置"""
    proxy = {}

    # 1. 检查环境变量
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    if http_proxy:
        proxy['http'] = http_proxy
    if https_proxy:
        proxy['https'] = https_proxy
    if proxy:
        return proxy

    # 2. Windows 注册表
    if platform.system() == 'Windows':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')
            proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
            proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
            winreg.CloseKey(key)
            if proxy_enable and proxy_server:
                # proxy_server 格式可能是 "127.0.0.1:7890" 或 "http=127.0.0.1:7890;https=127.0.0.1:7890"
                if 'http=' in proxy_server or 'https=' in proxy_server:
                    for part in proxy_server.split(';'):
                        if '=' in part:
                            proto, addr = part.split('=', 1)
                            proxy[proto] = f"http://{addr}"
                else:
                    proxy['http'] = f"http://{proxy_server}"
                    proxy['https'] = f"http://{proxy_server}"
                return proxy
        except Exception:
            pass

    # 3. macOS 系统代理 (networksetup)
    if platform.system() == 'Darwin':
        try:
            import subprocess
            result = subprocess.run(['networksetup', '-getwebproxy', 'Wi-Fi'],
                                    capture_output=True, text=True, timeout=3)
            output = result.stdout
            if 'Enabled: Yes' in output:
                lines = output.strip().split(chr(10))
                server = None
                port = None
                for line in lines:
                    if line.startswith('Server:'):
                        server = line.split(':')[1].strip()
                    elif line.startswith('Port:'):
                        port = line.split(':')[1].strip()
                if server and port:
                    proxy['http'] = f"http://{server}:{port}"
                    proxy['https'] = f"http://{server}:{port}"
                    return proxy
        except Exception:
            pass

    return None


def get_multi_ping_times_with_proxy(nodes, timeout):
    """带代理回退的多节点延迟检测

    先尝试 ICMP ping，如果失败且系统有代理设置，
    则通过代理发送 HTTP HEAD 请求测延迟。
    """
    from intertime import get_multi_ping_times
    results = get_multi_ping_times(nodes, timeout=timeout)

    proxy = get_system_proxy()
    if not proxy:
        return results

    # 安全导入 requests，未安装则跳过代理回退
    try:
        import requests
    except ImportError:
        return results

    for i, (node, ok, val) in enumerate(results):
        if ok:
            continue

        # ping 失败，尝试通过代理 HTTP 请求
        try:
            import time

            # 构造 URL
            if node.startswith('http://') or node.startswith('https://'):
                url = node
            else:
                url = f"http://{node}"

            start = time.time()
            resp = requests.head(url, timeout=timeout, proxies=proxy, allow_redirects=True)
            elapsed = int((time.time() - start) * 1000)

            # HTTP 2xx/3xx 都算通
            if resp.status_code < 400:
                results[i] = (node, True, elapsed)
        except Exception:
            pass

    return results

class IntertimeWorker(QThread):
    """网络延迟检测工作线程"""
    result_ready = pyqtSignal(list)

    def __init__(self, nodes, timeout):
        super().__init__()
        self.nodes = nodes
        self.timeout = timeout
        self._running = True

    def run(self):
        results = get_multi_ping_times_with_proxy(self.nodes, timeout=self.timeout)
        if self._running:
            self.result_ready.emit(results)

    def stop(self):
        self._running = False
        self.wait(1000)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.settings = SettingsManager()
        self.current_theme = self.settings.get('theme', 'dark')
        # === 网络延迟相关 ===
        self.intertime_timer = None
        self.intertime_nodes = []
        self.intertime_enabled = False
        self.intertime_interval = 5
        self.intertime_timeout = 2
        self.intertime_worker = None
        self.init_ui()
        self.load_logs()
        self.start_clock()
        self.init_intertime()
        self.apply_theme()

    def init_ui(self):
        self.setWindowTitle("HamLog - 业余无线电台日志管理系统")
        self.setMinimumSize(1200, 800)

        # ========== 菜单栏（修复版）==========
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # 导出 ADIF
        action_export_adif = QAction("导出 为ADIF文件", self)
        action_export_adif.setShortcut("Ctrl+E")
        action_export_adif.triggered.connect(self.open_export_dialog)
        file_menu.addAction(action_export_adif)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 日志菜单
        log_menu = menubar.addMenu("日志")
        add_action = QAction("添加日志", self)
        add_action.setShortcut(QKeySequence("Ctrl+N"))
        add_action.triggered.connect(self.open_add_dialog)
        log_menu.addAction(add_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")

        # 上传 LoTW
        action_upload_lotw = QAction("📡 上传到 LoTW...", self)
        action_upload_lotw.setShortcut("Ctrl+L")
        action_upload_lotw.triggered.connect(self.open_upload_dialog)
        tools_menu.addAction(action_upload_lotw)

        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        settings_action = QAction("软件设置", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图")
        toggle_theme_action = QAction("切换主题", self)
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        website_action = QAction("作者主页", self)
        website_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/1297822096?")))
        help_menu.addAction(website_action)

        github_action = QAction("GitHub", self)
        github_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/ARPRC-BA8AQA/HamLog")))
        help_menu.addAction(github_action)

        help_menu.addSeparator()

        open_folder_action = QAction("打开软件安装文件夹", self)
        open_folder_action.triggered.connect(self.open_install_folder)
        help_menu.addAction(open_folder_action)

        clear_db_action = QAction("清空数据库", self)
        clear_db_action.triggered.connect(self.clear_database)
        help_menu.addAction(clear_db_action)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 顶部信息栏
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setSpacing(20)

        # 左侧：呼号信息
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(5)

        self.callsign_label = QLabel("Your Callsign")
        self.callsign_label.setObjectName("title")
        self.callsign_label.setStyleSheet("font-size: 32px; color: #4fc3f7;")
        info_layout.addWidget(self.callsign_label)

        self.info_detail = QLabel("操作员：-  |  QTH：-  |  网格：-")
        self.info_detail.setObjectName("subtitle")
        info_layout.addWidget(self.info_detail)

        top_layout.addWidget(info_widget, stretch=1)

        # 中间：统计信息
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

        # 右侧：日期时间、网络延迟
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

        # 网络延迟 - 使用水平布局避免重叠
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

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3c3c3c;")
        main_layout.addWidget(line)

        # 工具栏
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

        # 日志表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(16)
        self.log_table.setHorizontalHeaderLabels([
            "ID", "呼号", "频率", "年", "月", "日", "时间", "模式",
            "我的功率", "对方功率", "给我报告", "我给报告", "QTH", "设备",
            "收到QSL", "发出QSL"
        ])
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.log_table.setColumnHidden(0, True)
        self.log_table.doubleClicked.connect(self.on_table_double_click)
        self.log_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self.show_context_menu)

        main_layout.addWidget(self.log_table)

        # 底部状态栏
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")

        self.load_station_info()

    def apply_theme(self):
        """应用当前主题"""
        if self.current_theme == 'light':
            self.setStyleSheet(StyleSheet.LIGHT)
        else:
            self.setStyleSheet(StyleSheet.DARK)

    def toggle_theme(self):
        """切换主题"""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.settings.set('theme', self.current_theme)
        self.apply_theme()
        # 刷新所有子窗口样式
        for widget in self.findChildren(QWidget):
            widget.setStyleSheet(self.styleSheet())

    # def start_intertime(self):
    #     # global intertime
    #     intertime = get_ping_time("127.0.0.1")
    #     self.update_intertime()


    def init_intertime(self):
        """初始化网络延迟检测"""
        # 从设置读取配置
        self.intertime_enabled = self.settings.get('intertime_enabled', '1') == '1'
        raw_nodes = self.settings.get('intertime_nodes', 'www.baidu.com')
        self.intertime_node_entries = [n.strip() for n in raw_nodes.split(',') if n.strip()][:5]

        # 解析出纯地址（去掉别名）用于 ping
        self.intertime_nodes = []
        for entry in self.intertime_node_entries:
            if ' (' in entry and entry.endswith(')'):
                addr = entry.split(' (')[0]
            else:
                addr = entry
            self.intertime_nodes.append(addr)

        self.intertime_timeout = int(self.settings.get('intertime_timeout', '2') or '2')
        self.intertime_interval = int(self.settings.get('intertime_interval', '5') or '5')

        # 创建定时器
        self.intertime_timer = QTimer(self)
        self.intertime_timer.timeout.connect(self._start_intertime_worker)

        if self.intertime_enabled and self.intertime_nodes:
            self.intertime_timer.start(self.intertime_interval * 1000)
            self._start_intertime_worker()  # 立即执行一次
        else:
            self.intertime_label.setText("已关闭")
            self.intertime_label.setStyleSheet("color: #666;")
            self.intertime_icon.setStyleSheet("color: #666; font-size: 10px;")

    def _start_intertime_worker(self):
        """启动网络延迟检测工作线程"""
        if not self.intertime_enabled or not self.intertime_nodes:
            return
        if self.intertime_worker and self.intertime_worker.isRunning():
            return
        self.intertime_worker = IntertimeWorker(self.intertime_nodes, self.intertime_timeout)
        self.intertime_worker.result_ready.connect(self._on_intertime_result)
        self.intertime_worker.start()

    def _on_intertime_result(self, results):
        """处理网络延迟检测结果"""
        if not self.intertime_enabled:
            return

        # 使用 init_intertime 中解析好的带别名节点列表
        node_entries = self.intertime_node_entries

        # 解析 "地址 (别名)" 格式
        nodes_with_alias = []
        for entry in node_entries:
            if ' (' in entry and entry.endswith(')'):
                addr = entry.split(' (')[0]
                alias = entry[entry.rfind(' (')+2:-1]
            else:
                addr = entry
                alias = None
            nodes_with_alias.append((addr, alias))

        # 构建显示文本
        parts = []
        all_ok = True
        for i, (node, ok, val) in enumerate(results):
            if i < len(nodes_with_alias):
                addr, alias = nodes_with_alias[i]
                # 优先使用别名
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

        # 根据状态设置颜色
        if all_ok:
            self.intertime_label.setStyleSheet("color: #81c784;")
            self.intertime_icon.setStyleSheet("color: #4caf50; font-size: 10px;")
        else:
            self.intertime_label.setStyleSheet("color: #ffb74d;")
            self.intertime_icon.setStyleSheet("color: #ff9800; font-size: 10px;")

    def restart_intertime(self):
        """重新启动网络延迟检测(设置变更后调用)"""
        if self.intertime_worker and self.intertime_worker.isRunning():
            self.intertime_worker.stop()
        if self.intertime_timer:
            self.intertime_timer.stop()
        self.init_intertime()




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
        self.update_stats()
        self.statusbar.showMessage("共 " + str(len(logs)) + " 条记录")

    def populate_table(self, logs):
        self.log_table.setRowCount(len(logs))

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

            self.log_table.setRowHeight(row, 28)

    def update_stats(self):
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
        # 网络延迟由独立定时器更新

    def search_logs(self):
        keyword = self.search_edit.text().strip()
        if not keyword:
            self.load_logs()
            return

        logs = self.db.search(keyword)
        self.populate_table(logs)
        self.statusbar.showMessage('搜索 "' + keyword + '" 找到 ' + str(len(logs)) + ' 条记录')

    def open_add_dialog(self):
        dialog = LogDialog(mode="add", parent=self)
        dialog.log_saved.connect(self.load_logs)
        dialog.exec()

    def open_edit_dialog(self, log_id):
        log_data = self.db.get_by_id(log_id)
        if log_data:
            dialog = LogDialog(mode="edit", log_data=log_data, parent=self)
            dialog.log_saved.connect(self.load_logs)
            dialog.exec()

    def open_view_dialog(self, log_id):
        log_data = self.db.get_by_id(log_id)
        if log_data:
            dialog = LogDialog(mode="view", log_data=log_data, parent=self)
            dialog.exec()

    def open_export_dialog(self):
        """打开导出 ADIF 对话框"""
        # 从 Database 实例获取数据库路径
        db_path = self.db.db_path
        dialog = ADIFExportDialog(db_path=db_path, parent=self)
        dialog.exec()

    def open_upload_dialog(self):
        """打开上传 LoTW 对话框"""
        dialog = LoTWUploadDialog(parent=self)
        dialog.exec()

    def on_table_double_click(self, index):
        row = index.row()
        log_id = int(self.log_table.item(row, 0).text())
        self.open_edit_dialog(log_id)

    def show_context_menu(self, position):
        row = self.log_table.rowAt(position.y())
        if row < 0:
            return

        log_id = int(self.log_table.item(row, 0).text())
        callsign = self.log_table.item(row, 1).text()

        menu = QMenu(self)

        view_action = QAction("查看 " + callsign, self)
        view_action.triggered.connect(lambda: self.open_view_dialog(log_id))
        menu.addAction(view_action)

        edit_action = QAction("编辑 " + callsign, self)
        edit_action.triggered.connect(lambda: self.open_edit_dialog(log_id))
        menu.addAction(edit_action)

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
                QMessageBox.information(self, "成功", msg)
                self.load_logs()
            else:
                QMessageBox.warning(self, "失败", msg)

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self.load_station_info)
        dialog.theme_changed.connect(self.on_theme_changed)
        dialog.intertime_settings_changed.connect(self.restart_intertime)
        dialog.exec()

    def on_theme_changed(self, new_theme):
        self.current_theme = new_theme
        self.apply_theme()

    def show_about(self):
        QMessageBox.about(self, "关于 ",
                          "<h2>HamLog 业余无线电台日志管理系统</h2>"
                          "<p>版本：内部--Alpha1</p>"
                          "<p>作者：BA8AQA</p>"
                          "<p>Bilibili:https://space.bilibili.com/1297822096?</p>"
                          "<p>Github:https://github.com/ARPRC-BA8AQA/HamLog</p>"
                          "<p>基于 Python、PyQt6、SQLite 开发</p>"
                          "<p>本软件遵循GPL3协议</p>"
                          "<p>特别鸣谢：BA8AQA    BG5JQN和所有对HamLog开发做出过贡献的人和组织</p>"
                          "<p>73!</p>")

    def open_install_folder(self):
        """用系统文件管理器打开软件所在文件夹"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后
            app_dir = Path(sys.executable).parent
        else:
            # 开发环境
            app_dir = Path(__file__).parent

        path = str(app_dir.resolve())

        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{path}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件夹:\n{e}")

    def clear_database(self):
        """清空数据库"""
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
                    # 关闭现有连接
                    self.db.close()
                    self.settings.close()

                    # 删除数据库文件（路径来自 AutoDeal.db_path）
                    db_file = Path(self.db.db_path)
                    if db_file.exists():
                        db_file.unlink()

                    # 重新初始化
                    self.db = Database()
                    self.settings = SettingsManager()

                    # 刷新界面
                    self.load_logs()
                    self.load_station_info()

                    QMessageBox.information(self, "完成", "数据库已清空并重新初始化。")

                except Exception as e:
                    QMessageBox.critical(self, "错误", f"清空失败:\n{e}")
                    # 尝试恢复连接
                    try:
                        self.db = Database()
                        self.settings = SettingsManager()
                    except:
                        pass

    def closeEvent(self, event):
        if self.intertime_worker and self.intertime_worker.isRunning():
            self.intertime_worker.stop()
        if self.intertime_timer:
            self.intertime_timer.stop()
        self.db.close()
        self.settings.close()
        event.accept()


def main():
    # 确保 pkgutil 可用（PyInstaller 打包兼容性）
    try:
        import pkgutil
    except ImportError:
        import traceback
        traceback.print_exc()
        print("错误: 缺少 pkgutil 模块。请尝试以下解决方案:")
        print("1. 升级 PyInstaller: pip install --upgrade pyinstaller")
        print("2. 打包时添加: --hidden-import pkgutil")
        print("3. 使用 .spec 文件打包，在 Analysis 中添加 hiddenimports=['pkgutil']")
        sys.exit(1)

    app = QApplication(sys.argv)

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()